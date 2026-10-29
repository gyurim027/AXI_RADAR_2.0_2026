"""종 아이콘 알림 만들기 (I-03, AD-00 3-1). DB 없이 도는 부분만 — 무엇을 알릴지 정한다.

실패 알림은 job_run이 실패할 때 바로 71에 남긴다(app/core/job_run.py). 나머지 셋은 원인 표를 보고 여기서 만든다.
    staleData  : 56 source_list — 주기가 정해진 자료인데 다음 갱신 예정일이 오늘보다 앞 (대시보드 '기준일 지난 자료'와 같은 기준)
    regulation : 89 standard_change — 운영자가 아직 확인하지 않은(seen_at 비어 있음) 규정 변경
    approval   : 62 setting_version — 최근 승인·반려된 제안 (화면 문구는 '반려', DB 값은 '돌려보냄')
같은 알림은 (종류, 표, 번호)로 한 번만 남는다 (71 UNIQUE uq_alert_delivery_ref). 읽음은 71 acknowledged_at에 남는다.
원인이 풀리면(자료를 다시 올림 · 규정 변경 화면에서 확인함) 안 읽은 알림은 '해결됨'으로 닫힌다.
"""
from __future__ import annotations

KINDS = ("failure", "staleData", "regulation", "approval")
CLOSE_WHEN_GONE = ("staleData", "regulation")      # 원인이 사라지면 닫는 종류 (승인 결과는 한 번 알리면 끝)
MAX_MESSAGE = 300                                   # 71 message VARCHAR(300)


def _cut(s: str) -> str:
    s = " ".join(s.split())
    return s if len(s) <= MAX_MESSAGE else s[: MAX_MESSAGE - 1] + "…"


def _day(d) -> str:
    return d.strftime("%Y.%m.%d") if hasattr(d, "strftime") else str(d or "")


def plan(stale: list[dict], changes: list[dict], decided: list[dict]) -> list[dict]:
    """원인 표의 줄 → 지금 있어야 하는 알림 [{kind, ref_table, ref_id, message}]"""
    out = []
    for s in stale:
        due = s.get("next_refresh_date")
        name = s.get("dataset") or s["source_id"]
        out.append({"kind": "staleData", "ref_table": "source_list",
                    "ref_id": f"{s['source_id']}@{due.isoformat() if hasattr(due, 'isoformat') else due}",
                    "message": _cut(f"{name}의 갱신 예정일({_day(due)})이 지났습니다. 새 자료를 받아 올려 주세요.")})
    for c in changes:
        where = f" {c['where_text']}" if c.get("where_text") else ""
        out.append({"kind": "regulation", "ref_table": "standard_change", "ref_id": str(c["standard_change_id"]),
                    "message": _cut(f"{c['doc_name']}{where} ({c['change_type']}) — 바뀐 내용을 확인해 주세요.")})
    for v in decided:
        kind = v.get("setting_kind") or "설정"
        name = "담당 부서 표 수정안" if kind == "담당 부서 표" else f"{kind} {v.get('version_label') or ''}".strip()
        if v["approval_status"] == "승인":
            tail = "" if kind == "담당 부서 표" else " 다음 산정부터 사용할 수 있습니다."
            msg = f"{name} 제안이 승인되었습니다.{tail}"
        else:
            msg = f"{name} 제안이 반려되었습니다. 사유를 확인해 주세요."
        out.append({"kind": "approval", "ref_table": "setting_version", "ref_id": str(v["setting_version_id"]),
                    "message": _cut(msg)})
    return out
