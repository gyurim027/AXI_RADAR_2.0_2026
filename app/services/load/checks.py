"""9장 적재 전 검사 8가지. 1~6번이 하나라도 걸리면 적재하지 않고, 7·8번은 경고로 기록만 한다."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Mapping, Sequence

from app.services.load.masking import has_pii


@dataclass
class CheckReport:
    failures: list[str] = field(default_factory=list)
    top50_overlap: int | None = None
    top50_total: int = 0
    low_heavy_cells: int = 0

    @property
    def passed(self) -> bool:
        return not self.failures


def _top50(counts: Counter) -> set[str]:
    return {g for g, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:50]}


def run_checks(records: Sequence[dict], period_start: date, db_receipts: Mapping[str, str],
               existing: Mapping[str, dict]) -> CheckReport:
    rep = CheckReport()
    ids = [r["complaint_id"] for r in records]

    # 1 민원ID 중복 (파일 안 · DB의 다른 민원)
    n = len(ids) - len(set(ids))
    n += sum(1 for r in records if r["complaint_id"] in existing and
             (existing[r["complaint_id"]].get("source_receipt_no") != r["source_receipt_no"]
              or existing[r["complaint_id"]].get("source_type") != r["source_type"]))
    if n:
        rep.failures.append(f"민원ID 중복 {n}건")

    # 2 원천_접수번호 중복 (파일 안 · DB의 다른 민원)
    receipts = [r["source_receipt_no"] for r in records if r["source_receipt_no"]]
    n = len(receipts) - len(set(receipts))
    n += sum(1 for r in records if r["source_receipt_no"] and db_receipts.get(r["source_receipt_no"], r["complaint_id"]) != r["complaint_id"])
    if n:
        rep.failures.append(f"접수번호 중복 {n}건")

    # 3 처리일 ≥ 접수일
    n = sum(1 for r in records if r["processed_date"] and r["received_date"] and r["processed_date"] < r["received_date"])
    if n:
        rep.failures.append(f"처리일이 접수일보다 빠른 민원 {n}건")

    # 4 기간의 월 = 접수일의 월 (파일 이름에서 월을 읽을 수 없어 올릴 때 적은 기간을 기준으로 함)
    ym = f"{period_start.year:04d}-{period_start.month:02d}"
    n = sum(1 for r in records if not r["received_date"] or r["received_date"][:7] != ym)
    if n:
        rep.failures.append(f"접수일이 기간의 월과 다른 민원 {n}건")

    # 5 좌표·gid·정확도 어긋남
    n = sum(1 for r in records if (r["gid"] and r["lat"] is None) or (r["coord_accuracy"] and not r["gid"]))
    if n:
        rep.failures.append(f"좌표·격자·정확도가 어긋난 민원 {n}건")

    # 6 저장 칸에 개인정보 꼴
    n = sum(1 for r in records if has_pii(r["location_text"]) or has_pii(r["report_type_raw"]) or has_pii(r["masked_summary"]))
    if n:
        rep.failures.append(f"저장 칸에 개인정보 꼴이 남은 민원 {n}건")

    # 7 낮음 포함/제외 상위 50칸 겹침 (경고)
    all_cnt = Counter(r["gid"] for r in records if r["gid"])
    ex_cnt = Counter(r["gid"] for r in records if r["gid"] and r["coord_accuracy"] != "낮음")
    a, b = _top50(all_cnt), _top50(ex_cnt)
    rep.top50_total = len(a)
    rep.top50_overlap = len(a & b)

    # 8 한 칸에 몰린 낮음 (경고): 30건 이상인 칸 중 낮음이 30% 이상
    low_cnt = Counter(r["gid"] for r in records if r["gid"] and r["coord_accuracy"] == "낮음")
    rep.low_heavy_cells = sum(1 for g, c in all_cnt.items() if c >= 30 and low_cnt[g] / c >= 0.3)
    return rep
