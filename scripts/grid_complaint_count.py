"""C-07 장소별 반복 민원 세기 — 78 priority_candidate의 complaint_cnt · complaint_cnt_excl_low.

정해진 규칙 (v0.5.3 C-06 예외, ISS-033)
  - 좌표 정확도 '낮음' 민원도 격자 민원 수에 넣는다 → complaint_cnt
  - 뺀 값도 함께 저장한다                           → complaint_cnt_excl_low
설정으로 바꿀 수 있는 것 (기능정의서 C-07 확인 후 정하기)
  --dedupe        중복 플래그가 있는 동일 민원을 한 번만 센다 (확정 정책 필요)
  --relevance     AI-01의 '보행안전 관련'만 센다. 미분류 전건은 오류로 중단; '불명' 제외
  --ai03 <폴더>   AI-03 민원 좌표(ai03_v2_update_79_complaint.csv)를 넣고 센다

사용법 (저장소 루트에서, uv run python -m scripts.<이 파일 이름>)
  python c07_complaint_count.py --ai03 ai03_updates
결과: out/c07_complaint_count.csv (gid, complaint_cnt, complaint_cnt_excl_low)
"""
import sys
from pathlib import Path
import pandas as pd
from app.services.grid import config as C, source as S
if "--csv" in sys.argv:                          # DB 대신 v2 CSV 폴더 읽기
    S.use_csv(sys.argv[sys.argv.index("--csv") + 1])

COLS = ["complaint_id", "gid", "coord_accuracy", "dup_flag", "relevance", "location_text", "report_type_raw",
        "received_date", "occurred_at", "source_type"]


def load(ai03_dir: Path | None) -> pd.DataFrame:
    c = S.read("src_complaint", usecols=COLS)
    if ai03_dir and (ai03_dir / "ai03_v2_update_79_complaint.csv").exists():
        u = pd.read_csv(ai03_dir / "ai03_v2_update_79_complaint.csv")
        u = u[u["complaint_id"].isin(c.loc[c["gid"].isna(), "complaint_id"])]      # 좌표가 빈 민원만
        c = c.set_index("complaint_id")
        c.loc[u["complaint_id"], "gid"] = u.set_index("complaint_id")["gid"]
        c.loc[u["complaint_id"], "coord_accuracy"] = u.set_index("complaint_id")["coord_accuracy"]
        c = c.reset_index()
        print(f"[AI-03] 민원 {len(u)}건 좌표 채움")
    return c


def count(c: pd.DataFrame, dedupe=False, relevance=False) -> pd.DataFrame:
    """Count complaints for C-07; strict relevance mode never falls back to all rows.

    C-07's historical unfiltered count remains a descriptive inventory only.
    A score-consuming caller MUST use relevance=True and separately verify the
    approved classification/period/location/dedup provenance; these counts
    alone do not establish official eligibility.
    """
    required = {"complaint_id", "gid", "coord_accuracy", "dup_flag", "relevance"}
    if not required.issubset(c.columns):
        raise ValueError("C07_MISSING_COLUMNS:" + ",".join(sorted(required-set(c.columns))))
    if c["complaint_id"].isna().any() or c["complaint_id"].duplicated().any():
        raise ValueError("C07_INVALID_COMPLAINT_ID")
    d = c[c["gid"].notna()].copy()
    if relevance:
        # AI-01 actual values are '보행안전 관련', '비관련', '불명'.
        # Unknown/unclassified records are never counted as eligible.
        labels = d["relevance"].dropna().astype(str).str.strip()
        unexpected = set(labels.unique()) - {"보행안전 관련", "비관련", "불명"}
        if unexpected:
            raise ValueError("C07_UNKNOWN_RELEVANCE_VOCABULARY")
        if c["relevance"].isna().all():
            raise ValueError("C07_CLASSIFICATION_UNAVAILABLE")
        d = d[d["relevance"].eq("보행안전 관련")]
    if dedupe:
        key = ["gid", "location_text", "report_type_raw", "received_date", "occurred_at", "source_type"]
        missing = sorted(set(key)-set(d.columns))
        if missing:
            raise ValueError("C07_DEDUPE_KEYS_MISSING:" + ",".join(missing))
        dup = d[d["dup_flag"].notna()].drop_duplicates(subset=key)
        d = pd.concat([d[d["dup_flag"].isna()], dup])
    grid = S.read("grid_cell", usecols=["gid"])
    if grid["gid"].isna().any() or grid["gid"].duplicated().any():
        raise ValueError("C07_INVALID_GRID_KEYS")
    out = grid.assign(
        complaint_cnt=grid["gid"].map(d.groupby("gid").size()).fillna(0).astype(int),
        complaint_cnt_excl_low=grid["gid"].map(d[d["coord_accuracy"] != "낮음"].groupby("gid").size()).fillna(0).astype(int))
    return out


if __name__ == "__main__":
    ai03 = Path(sys.argv[sys.argv.index("--ai03") + 1]) if "--ai03" in sys.argv else None
    base = count(load(None), "--dedupe" in sys.argv, "--relevance" in sys.argv)
    out = count(load(ai03), "--dedupe" in sys.argv, "--relevance" in sys.argv) if ai03 else base
    out.to_csv(C.OUT_DIR / "c07_complaint_count.csv", index=False, encoding="utf-8-sig")
    print(f"저장: out/c07_complaint_count.csv ({len(out)}칸)")
    print(f"민원 수 합: {out['complaint_cnt'].sum():,}건 (낮음 제외 {out['complaint_cnt_excl_low'].sum():,}건), "
          f"민원 있는 칸 {(out['complaint_cnt'] > 0).sum():,}칸")
    if ai03:
        d = out["complaint_cnt"] - base["complaint_cnt"]
        print(f"[AI-03 전후] 민원 {d.sum():,}건이 {(d > 0).sum()}칸에 새로 붙음 "
              f"(낮음 제외 값은 {(out['complaint_cnt_excl_low'] - base['complaint_cnt_excl_low']).sum():,}건 증가)")
