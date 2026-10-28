"""RADAR AI-10 공통 평가 연결 어댑터.

run_text: 평가 입력의 명시적 CK 참조 및 근거 상태를 CaseInput으로 옮겨
          기존 사례 기반 초안 생성 함수를 호출합니다. 모델 경로는 공통 LLM 설정을 따릅니다.
run_dept: F-01 담당 부서 판정 함수가 확인되면 환경변수로 연결합니다.

이 모듈은 정답 CSV를 읽지 않으며, 미확인 사실을 확정 관측으로 변환하지 않습니다.
"""
from __future__ import annotations

import importlib
import os
import re
from typing import Any, Callable


def _load_resolver(env_key: str) -> Callable[[str], Any]:
    spec = os.environ.get(env_key, "").strip()
    if not spec or ":" not in spec:
        raise RuntimeError(f"{env_key} 미설정: 실제 기능의 '모듈:함수' 경로가 필요합니다.")
    module_name, function_name = spec.rsplit(":", 1)
    func = getattr(importlib.import_module(module_name), function_name)
    if not callable(func):
        raise TypeError(f"{env_key}: 호출 가능한 함수가 아닙니다.")
    return func


def _extract(output: Any, keys: tuple[str, ...], label: str) -> str | None:
    if isinstance(output, dict):
        for key in keys:
            if key in output:
                output = output[key]
                break
        else:
            raise ValueError(f"{label} 결과에 필요한 키가 없습니다: {keys}")
    if output is None:
        return None
    if not isinstance(output, str):
        raise TypeError(f"{label} 결과는 문자열 또는 None이어야 합니다.")
    return output.strip() or None


def run_dept(input_text: str) -> str | None:
    """F-01 등 실제 담당 부서 판정기를 사용. 임의의 부서를 생성하지 않습니다."""
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("평가 입력이 비었습니다.")
    output = _load_resolver("AI10_EVAL_DEPT_RESOLVER")(input_text)
    return _extract(output, ("receiving_department",), "부서")


def _case_module():
    """실제 프로젝트 배치 경로가 다른 경우 두 경로를 순서대로 확인합니다."""
    errors = []
    for path in ("app.services.ai10_case_draft", "app.services.AI-10.ai10_case_draft"):
        try:
            return importlib.import_module(path)
        except ModuleNotFoundError as exc:
            # 종속 패키지 누락은 숨기지 않습니다.
            if exc.name != path and not path.startswith((exc.name or "") + "."):
                raise
            errors.append(path)
    raise ModuleNotFoundError(f"AI-10 사례 초안 모듈을 찾지 못했습니다: {errors}")


def _evidence_state(description: str) -> str:
    """평가 문장에 명시된 근거 유형만 보수적으로 분류합니다."""
    if re.search(r"과거|\b20\d{2}년|이전\s*(기록|자료)", description):
        return "historical_record"
    if re.search(r"추정|추산|계산|산출", description):
        return "estimated_or_derived"
    # '도면에 측정치 없음' 등은 추정값 자체도 확보되지 않았습니다.
    return "missing"


def _to_case(input_text: str, case_module: Any) -> Any:
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("평가 입력이 비었습니다.")
    text = input_text.strip()
    match = re.match(r"^(CK-\d{1,2})\s*\|\s*(.+)$", text, re.DOTALL | re.I)
    if match:
        ck_reference = match.group(1).upper()
        description = match.group(2).strip()
    else:
        ck_reference = None
        description = text
    description = re.sub(r"^가상\s*후보\s*:\s*", "", description).strip()
    if not description:
        raise ValueError("상황 설명이 비었습니다.")
    state = _evidence_state(description)
    evidence = case_module.EvidenceItem(
        claim_or_finding=description,
        evidence_state=state,
    )
    return case_module.CaseInput(
        case_reference=f"eval-{ck_reference or 'no-ck'}",
        issue_description=description,
        evidence_items=[evidence],
        ck_reference=ck_reference,
    )


def run_text(input_text: str) -> str | None:
    """AI-10 개발용 사례 초안을 생성합니다. 공통 LLM의 내부/외부 경로 정책을 따릅니다."""
    module = _case_module()
    case = _to_case(input_text, module)
    result = module.generate_case_draft(case)
    if not isinstance(result, dict):
        raise TypeError("AI-10 생성 결과가 dict가 아닙니다.")
    if not result.get("model_call_allowed"):
        raise RuntimeError(f"AI-10 생성 조건 미충족: {result.get('reasons')}")
    draft = result.get("draft")
    if not isinstance(draft, dict):
        raise ValueError("AI-10 생성 결과에 draft가 없습니다.")
    return _extract(draft, ("draft_template",), "문장")


def run_structured_case(case_payload: dict, *, source_rows: list[dict] | None = None) -> dict:
    """근거 출처 필드를 보존하는 구조화 입력 경로 (문자열 평가와 별도).

    source_rows는 DB 56의 읽기 전용 조회 결과다. 목록이 없거나 검증되지 않은
    source_id는 실제 AI 입력에 넘기지 않는다. DB 56에 존재한다는 사실만으로
    그 컬럼의 원천임을 증명할 수 없으므로 최종 증빙은 별도 필요하다.
    """
    if not isinstance(case_payload, dict):
        raise TypeError("구조화 입력은 dict이어야 합니다.")
    if source_rows is None:
        raise ValueError("DB 56 source_list 조회 결과가 없어 출처 검증 불가")
    audit_evidence_sources = importlib.import_module("app.services.AI-10.ai10_source_provenance").audit_evidence_sources
    module = _case_module()
    case = module.CaseInput.model_validate(case_payload)
    report = audit_evidence_sources(case.evidence_items, source_rows)
    # 하나라도 출처를 식별하지 못하면 모델 호출 전에 중단한다.
    if report['issues']:
        return {'model_call_allowed': False, 'source_audit': report, 'draft': None, 'db_written': False}
    # 이 단계는 형식·목록 대조만 가능하다. 레코드 수준 원천 확정은 아직 불가.
    # 출처 검증 완료로 오인하는 실행을 막고, 실행 가능 입력만 보고한다.
    return {'model_call_allowed': False, 'source_audit': report, 'draft': None, 'db_written': False,
            'reason': '판정 레코드-원천자료 연결 근거 미확인'}
