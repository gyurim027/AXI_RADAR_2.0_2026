"""AI-10 external-bound CASE_JSON projection. Fail closed, no provider calls.

This projection is intentionally separate from internal build_case_prompt().
Public catalog status alone NEVER qualifies a record for external transfer.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

_SRC = re.compile(r"SRC\d{2}$")
_STATES = frozenset({"assessment_result", "estimated_or_derived", "historical_record", "confirmed_observation", "missing", "unverified_reference"})
# Explicitly disallow free-form user text, IDs, coordinates, geometry, and raw values.
_ALLOWED_FINDING_TYPES = frozenset({"width_under_threshold", "sight_obstruction_estimated", "assessment_requires_review"})


def make_external_projection(*, approved_case_token: str, reviewed_findings: Sequence[Mapping],
                             allowed_src_ids: set[str], source_access: Mapping[str, str]) -> dict:
    """Accept only separately reviewed, enumerated DERIVED findings.

    reviewed_findings entry: source_id, finding_type, evidence_state.
    No original CaseInput, claim_or_finding, raw_value, identifiers or geometry can pass through.
    The caller must supply previously approved allowed_src_ids, never infer it from DB labels.
    """
    if not isinstance(approved_case_token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", approved_case_token):
        raise ValueError("approved_case_token must be a non-identifying opaque token")
    if not reviewed_findings or not isinstance(reviewed_findings, (list, tuple)):
        raise ValueError("reviewed_findings required")
    if not isinstance(allowed_src_ids, set) or not isinstance(source_access, Mapping):
        raise ValueError("explicit allowlist and access metadata required")

    safe = []
    for finding in reviewed_findings:
        if not isinstance(finding, Mapping) or set(finding) != {"source_id", "finding_type", "evidence_state"}:
            raise ValueError("finding must contain exactly approved structured fields")
        sid, kind, state = (finding[k] for k in ("source_id", "finding_type", "evidence_state"))
        if not isinstance(sid, str) or not _SRC.fullmatch(sid) or sid not in allowed_src_ids:
            raise ValueError("unapproved or unknown SRC")
        level = source_access.get(sid)
        # '공개 (팀 내부...)' or '공개 (출처... 원본 국외 반출 금지)' is NOT unconditionally public.
        if level != "공개":
            raise ValueError("SRC is not unconditionally public")
        if kind not in _ALLOWED_FINDING_TYPES or state not in _STATES:
            raise ValueError("non-reviewed finding kind/state")
        safe.append({"source_id": sid, "finding_type": kind, "evidence_state": state})
    return {"case_token": approved_case_token, "findings": safe, "data_ids": sorted({r["source_id"] for r in safe})}


def render_external_case_json(**kwargs) -> str:
    return json.dumps(make_external_projection(**kwargs), ensure_ascii=False, separators=(",", ":"))
