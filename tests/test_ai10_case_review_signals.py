import importlib
from types import SimpleNamespace

import pytest


signals = importlib.import_module(
    "app.services.ai10.ai10_case_review_signals"
)


def make_case(states=("confirmed_observation",), claim="", **kwargs):
    return SimpleNamespace(
        evidence_items=[
            SimpleNamespace(
                evidence_state=state,
                raw_value=claim,
                claim_or_finding=claim,
            )
            for state in states
        ],
        issue_description=kwargs.get("issue_description", ""),
        problem_type_text=kwargs.get("problem_type_text", ""),
        assessment=kwargs.get("assessment", ""),
        law_references=kwargs.get("law_references", []),
    )


def check(case, sentence):
    output = SimpleNamespace(draft_template=sentence)
    return {
        item["code"]
        for item in signals.collect_review_signals(case, output)
    }


@pytest.mark.parametrize(
    "state",
    [
        "reported_claim",
        "historical_record",
        "estimated_or_derived",
        "missing",
        "unverified_reference",
    ],
)
def test_limited_evidence_requires_review(state):
    codes = check(make_case((state,)), "현장 확인이 필요합니다.")
    assert "EVIDENCE_LIMITATION_REVIEW" in codes


def test_legal_assertion_requires_review():
    codes = check(
        make_case(),
        "해당 시설은 법령 위반으로 판단됩니다.",
    )
    assert "LEGAL_ASSERTION_REVIEW" in codes


def test_unverified_facility_state_requires_review():
    codes = check(
        make_case(("reported_claim",)),
        "점자블록이 설치되어 있지 않습니다.",
    )
    assert "UNVERIFIED_STATE_REVIEW" in codes


def test_unsourced_number_requires_review():
    codes = check(
        make_case(claim="현장 점검이 필요함"),
        "보도 유효폭이 1.5m입니다.",
    )
    assert "UNSOURCED_NUMBER_REVIEW" in codes


def test_sourced_number_does_not_trigger_unsourced_flag():
    codes = check(
        make_case(claim="보도 유효폭 1.5m 측정"),
        "보도 유효폭이 1.5m입니다.",
    )
    assert "UNSOURCED_NUMBER_REVIEW" not in codes


def test_law_reference_requires_review():
    codes = check(
        make_case(
            law_references=[
                {"article": "reference candidate"}
            ]
        ),
        "적용 기준을 검토해야 합니다.",
    )
    assert "LAW_REFERENCE_REVIEW" in codes


def test_clean_case_does_not_raise_signals():
    codes = check(
        make_case(claim="시설 상태 확인 완료"),
        "확인된 시설 상태를 검토했습니다.",
    )
    assert codes == set()
