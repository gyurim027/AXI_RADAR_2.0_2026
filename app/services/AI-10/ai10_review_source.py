
"""AI-10 H-07 서버 보관 검토 기록 확인.

개발용 JSON의 검토 신호와 승인 이력을 검사한다.
운영 DB 승인 가능 여부는 항상 False이다.
"""

from pathlib import Path
from importlib import import_module


class ReviewSourceError(ValueError):
    pass


def inspect_review_source(item_id: str, store: Path) -> dict:
    if not isinstance(item_id, str) or not item_id.strip():
        raise ReviewSourceError("Invalid review item ID")

    module = import_module("app.services.AI-10.ai10_operator_review")
    data = module.load_store(Path(store))

    items = data.get("items")
    if not isinstance(items, dict):
        raise ReviewSourceError("Invalid review storage")

    item = items.get(item_id)
    if not isinstance(item, dict):
        raise ReviewSourceError("Review item not found")

    if item.get("rule_id") != item_id:
        raise ReviewSourceError("Review item ID mismatch")

    findings = item.get("findings")
    if not isinstance(findings, list):
        raise ReviewSourceError("Review findings unavailable")

    for finding in findings:
        if not isinstance(finding, dict) or not all(
            isinstance(finding.get(key), str) and finding[key].strip()
            for key in ("code", "category", "detail")
        ):
            raise ReviewSourceError("Invalid review finding")

    events = item.get("events")
    if not isinstance(events, list):
        raise ReviewSourceError("Review events unavailable")

    if any(not isinstance(event, dict) for event in events):
        raise ReviewSourceError("Invalid review event")

    approved = (
        item.get("approved") is True
        and item.get("review_status") == "approved"
    )

    approval_history_verified = False

    if approved:
        if not events or events[-1].get("action") != "approve":
            raise ReviewSourceError(
                "Current approval has no matching latest event"
            )

        event = events[-1]

        if (
            not isinstance(event.get("evidence_source"), str)
            or not event["evidence_source"].strip()
            or event.get("evidence_checked_by_reviewer") is not True
        ):
            raise ReviewSourceError(
                "Approval evidence verification record missing"
            )

        if (
            type(event.get("finding_count_at_decision")) is not int
            or event["finding_count_at_decision"] != len(findings)
        ):
            raise ReviewSourceError(
                "Approval finding count mismatch"
            )

        if findings and event.get("findings_acknowledged") is not True:
            raise ReviewSourceError(
                "Review findings were not acknowledged"
            )

        if (
            not isinstance(event.get("note"), str)
            or not event["note"].strip()
            or not isinstance(event.get("reviewer"), str)
            or not event["reviewer"].strip()
            or event["reviewer"] != item.get("reviewer")
            or not isinstance(event.get("at"), str)
            or not event["at"].strip()
            or not isinstance(item.get("approved_at"), str)
            or not item["approved_at"].strip()
            or type(event.get("revision")) is not int
            or event["revision"] != item.get("revision")
        ):
            raise ReviewSourceError(
                "Approval event and current review state mismatch"
            )

        approval_history_verified = True

    return {
        "item_id": item_id,
        "has_findings": bool(findings),
        "finding_count": len(findings),
        "review_status": item.get("review_status"),
        "approved": approved,
        "source_verified": True,
        "approval_history_verified": approval_history_verified,
        "db_approval_ready": False,
    }
