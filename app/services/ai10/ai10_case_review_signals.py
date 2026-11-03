"""Case-based review signals. Human review only; no automatic approval."""
import re

NUMBER = re.compile(
    r"(?<!\w)\d+(?:[.,]\d+)?\s*(?:km|m|%|\uCD08|\uAC74|\uACF3)"
)

LEGAL = re.compile(
    r"(?:\uBC95\uB839\s*\uC704\uBC18|"
    r"\uBC95\uB960\s*\uC704\uBC18|"
    r"\uC704\uBC18\uC774\s*\uD655\uC815|"
    r"\uBC18\uB4DC\uC2DC\s*\uC124\uCE58\uD574\uC57C)"
)

FACILITIES = (
    "\uc2dc\uc124", "\uc810\uc790\ube14\ub85d", "\ud45c\uc9c0\ud310",
    "\ubcfc\ub77c\ub4dc", "\uc2e0\ud638\ub4f1", "\uad50\ud1b5\uc12c",
    "\uce74\uba54\ub77c", "\ubcf4\uc548\ub4f1", "\uc6b8\ud0c0\ub9ac",
)

STATE_ENDINGS = (
    "\uc124\uce58\ub418\uc5b4 \uc788\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4",
    "\ud30c\uc190\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4",
    "\uace0\uc7a5\ub0ac\uc2b5\ub2c8\ub2e4",
    "\uc874\uc7ac\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4",
)

STATE = re.compile(
    "(?:" + "|".join(map(re.escape, FACILITIES)) + ")"
    ".{0,35}(?:"
    + "|".join(
        re.escape(term).replace(r"\ ", r"\s*")
        for term in STATE_ENDINGS
    )
    + ")"
)

LIMITED_STATES = {
    "reported_claim",
    "historical_record",
    "estimated_or_derived",
    "missing",
    "unverified_reference",
}


def collect_review_signals(case, output):
    findings = []
    sentence = output.draft_template
    evidence = case.evidence_items
    states = {item.evidence_state for item in evidence}

    def add(code, detail):
        findings.append({
            "code": code,
            "category": "review",
            "detail": detail,
        })

    if states & LIMITED_STATES:
        add(
            "EVIDENCE_LIMITATION_REVIEW",
            "Evidence limitations require human review.",
        )

    if LEGAL.search(sentence):
        add(
            "LEGAL_ASSERTION_REVIEW",
            "Check legal assertions and mandatory actions.",
        )

    if "confirmed_observation" not in states and STATE.search(sentence):
        add(
            "UNVERIFIED_STATE_REVIEW",
            "Check unverified facility state assertions.",
        )

    context = " ".join(
        str(value)
        for item in evidence
        for value in (item.raw_value, item.claim_or_finding)
        if value is not None
    )
    context += " " + str(case.issue_description or "")
    context += " " + str(case.problem_type_text or "")
    context += " " + str(case.assessment or "")

    normalized_context = re.sub(r"\s+", "", context)

    for number in sorted(set(NUMBER.findall(sentence))):
        if re.sub(r"\s+", "", number) not in normalized_context:
            add(
                "UNSOURCED_NUMBER_REVIEW",
                f"Numeric expression needs source review: {number}",
            )

    if case.law_references:
        add(
            "LAW_REFERENCE_REVIEW",
            "Check applicability of supplied legal references.",
        )

    return findings
