"""우선순위 결과 조회 (77 priority_run · 78 priority_candidate · 82 priority_candidate_action, SQL v2.1). 읽기만 한다.

- 점수 계산·후보 선정은 진규 산정 기능이 77·78에 쓴다. 여기서는 그 결과를 회차별로 읽어 화면·다른 기능에 준다.
- NULL은 NULL 그대로 (점수·순위가 없으면 0으로 바꾸지 않는다).
- 구는 05 grid_feature.id_gu('성남시 분당구')에서 '성남시 '를 뗀 이름. 구가 비어 있는 격자 44개는 gu=None.
"""
from __future__ import annotations

from app.core import db

CANDIDATE_COLS = ("run_id", "gid", "selected_yn", "score", "rank_no", "complaint_cnt", "complaint_cnt_excl_low",
                  "cond_result_yn", "cond_hazard_yn", "cond_exposure_yn", "cond_vulnerable_yn", "matched_roles", "note")
ACTION_COLS = ("item_id", "action_text", "dept_text", "basis_text", "created_at")

_GU = "NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '')"          # '성남시 분당구' → '분당구'


class PriorityRepository:
    def list_runs(self, limit: int) -> list[dict]:
        return db.read_only(
            "SELECT r.run_id, r.build_id, r.rule_version, r.created_at, r.note, "
            "COUNT(c.gid) AS candidate_cnt, SUM(c.selected_yn = 'Y') AS selected_cnt, "
            "SUM(c.score IS NOT NULL) AS scored_cnt "
            "FROM priority_run r LEFT JOIN priority_candidate c ON c.run_id = r.run_id "
            "GROUP BY r.run_id, r.build_id, r.rule_version, r.created_at, r.note "
            "ORDER BY r.created_at DESC, r.run_id DESC LIMIT %s", (limit,))

    def get_run(self, run_id: int) -> dict | None:
        rows = db.read_only("SELECT run_id, build_id, rule_version, created_at, note FROM priority_run "
                            "WHERE run_id = %s", (run_id,))
        return rows[0] if rows else None

    def list_candidates(self, run_id: int, gus: list[str] | None, include_no_gu: bool, selected: str | None,
                        limit: int, offset: int) -> tuple[list[dict], int]:
        """gus=None이면 구 제한 없음. include_no_gu=False면 구가 빈 격자는 뺀다(구 도로관리팀)."""
        where = ["c.run_id = %s"]
        args: list = [run_id]
        if gus is not None:
            gu_cond = f"{_GU} IN ({', '.join(['%s'] * len(gus))})" if gus else "FALSE"
            args.extend(gus)
            where.append(f"({gu_cond} OR {_GU} IS NULL)" if include_no_gu else gu_cond)
        elif not include_no_gu:
            where.append(f"{_GU} IS NOT NULL")
        if selected:
            where.append("c.selected_yn = %s")
            args.append(selected)
        base = ("FROM priority_candidate c LEFT JOIN grid_feature f ON f.ID_gid = c.gid WHERE " + " AND ".join(where))
        total = db.read_only("SELECT COUNT(*) AS n " + base, args)
        rows = db.read_only(
            "SELECT " + ", ".join("c." + k for k in CANDIDATE_COLS) + f", {_GU} AS gu, f.`ID_중심위도` AS center_lat, f.`ID_중심경도` AS center_lon " + base +
            " ORDER BY c.rank_no IS NULL, c.rank_no, c.gid LIMIT %s OFFSET %s", [*args, limit, offset])
        return rows, int(total[0]["n"]) if total else 0

    def get_candidate(self, run_id: int, gid: str) -> dict | None:
        rows = db.read_only(
            "SELECT " + ", ".join("c." + k for k in CANDIDATE_COLS) + f", {_GU} AS gu "
            "FROM priority_candidate c LEFT JOIN grid_feature f ON f.ID_gid = c.gid "
            "WHERE c.run_id = %s AND c.gid = %s", (run_id, gid))
        if not rows:
            return None
        cand = rows[0]
        from app.services.priority.details import read_evidence
        cand["details"] = read_evidence(db.read_only, run_id, gid)
        cand["actions"] = db.read_only(
            "SELECT " + ", ".join(ACTION_COLS) + " FROM priority_candidate_action "
            "WHERE run_id = %s AND gid = %s ORDER BY item_id", (run_id, gid))
        return cand


_repo: PriorityRepository = PriorityRepository()


def set_repository(repo: PriorityRepository) -> None:
    global _repo
    _repo = repo


def get_repository() -> PriorityRepository:
    return _repo
