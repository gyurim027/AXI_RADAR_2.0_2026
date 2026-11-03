"""신규 사례 기반 AI-10 검토용 상세 표시 (DB·API 변경 없음)."""
from __future__ import annotations
import textwrap

STATES = {
    'confirmed_observation': '확인된 관측', 'assessment_result': '판정 결과',
    'reported_claim': '신고·민원 주장', 'historical_record': '과거 기록',
    'estimated_or_derived': '추정·산출', 'missing': '자료 없음',
    'conflicting': '근거 상충', 'unverified_reference': '검증 전 참고 근거',
}

def _line(label: str, value: object) -> None:
    text = str(value) if value is not None else '없음'
    parts = text.splitlines() or ['']
    print(f'[{label}] {parts[0]}')
    for part in parts[1:]:
        print(' ' * (len(label) + 3) + part)


DETAIL_LABELS = ('문제 유형', '판정 결과', '문제 유형 참고', '시험 시설·격자', '신고인의 주장',
 '입력 근거·상태', '사실 확인', '미확인', '판정 기준', '자료 한계', '확인 사항', '조치 종류',
 '법령 근거 후보/검증 전', 'AI 생성 가능 여부', '생성 가능 여부 판단 이유', 'AI 모델',
 '문제 유형별 초안', '운영자 확인 메모', '최종 후보 조치 제안')

def print_ai10_detail(case_id: str, title: str, fields: dict) -> None:
    """AI-10 시험 콘솔의 단일 상세 출력 형식. 누락 항목은 추정하지 않는다."""
    print('=' * 72)
    print(f'{case_id} | {title}')
    for label in DETAIL_LABELS:
        _line(label, fields.get(label) if fields.get(label) not in (None, '') else '미입력 / 해당 없음')

def print_case_detail(case, result: dict) -> None:
    """신규 사례형 입력의 표시 변환. 판정·생성 조건 및 승인 상태는 수정하지 않는다."""
    claims=[e.claim_or_finding for e in case.evidence_items if e.evidence_state=='reported_claim']
    evidence=[f'{STATES.get(e.evidence_state,e.evidence_state)}: {e.claim_or_finding or "내용 미입력"}' for e in case.evidence_items]
    confirmed=[e.claim_or_finding for e in case.evidence_items if e.evidence_state=='confirmed_observation']
    # 미확인에는 확인해야 하는 사실, 자료 한계에는 근거의 제약을 적어 동일한 원문 중복을 막는다.
    missing_checks=[]
    limitations=[]
    for item in case.evidence_items:
        state=item.evidence_state
        if state=='reported_claim':
            missing_checks.append('신고 내용의 실제 존재 여부·구체적 위치·상태')
            limitations.append('신고 주장 외 확인된 현장 조사·측정 자료 없음')
        elif state=='historical_record':
            missing_checks.append('현재 시설 상태 및 과거 기록 이후 변경 여부')
            limitations.append('과거 기록으로 현재 상태를 확정할 수 없음'+(f' (기록일: {item.source_date})' if item.source_date else ''))
        elif state=='estimated_or_derived':
            missing_checks.append('추정값의 원천 근거·산출 조건 및 현장 일치 여부')
            limitations.append('추정·산출 결과로 현장 실측을 대체할 수 없음')
        elif state=='assessment_result':
            missing_checks.append('평가 적용 기준·입력 출처와 평가 후 상태')
            limitations.append('평가 결과만으로 현재 상태나 위반 여부를 확정할 수 없음')
        elif state=='confirmed_observation':
            missing_checks.append('관측 범위를 벗어난 상태·추가 정비 필요성' )
            limitations.append('입력된 관측 내용 외 측정 수치·정비 기준 등은 별도 확인 필요')
        elif state=='conflicting':
            missing_checks.append('자료 간 불일치 원인과 우선 확인할 사실')
            limitations.append('입력 근거가 서로 상충하여 현재 사실관계 확정 불가')
        elif state=='unverified_reference':
            missing_checks.append('참고자료 출처·효력·적용 대상')
            limitations.append('참고자료 검증 전')
        elif state=='missing':
            missing_checks.append('누락된 자료 및 실제 시설 상태')
            limitations.append('필요 근거 미입력')
    # 입력 자체가 없는 경우에만 미입력을 표시한다.
    uncertain=list(dict.fromkeys(missing_checks))
    limits=list(dict.fromkeys(limitations))
    labels={'ready_for_review_draft':'검토용 초안 생성 가능','limited_check_only':'확인 중심 초안만 허용',
      'requires_human_resolution':'사실관계 확인 필요','insufficient_input':'입력 정보 부족'}
    draft=result.get('draft')
    reference=(f'{case.ck_reference} / {result.get("ck_reference_status","참고 상태 미확인")}' if case.ck_reference
               else '없음 / 선택적 참고')
    # 모의 생성 여부와 실제 호출 여부는 result 상태값만으로 단정하지 않는다.
    model_state=result.get('model_display_status') or ('생성됨 (미승인) / 모의·실제 호출 구분 미제공' if draft else '미호출 / 생성 보류')
    fields={
      '문제 유형':case.problem_type_text or case.facility_type or '미분류',
      '판정 결과':case.assessment or '판정값 미입력',
      '문제 유형 참고':reference,
      '시험 시설·격자':f'{case.facility_id or "미연결"} / {case.gid or "미연결"} (가상 또는 미입력)',
      '신고인의 주장':' / '.join(claims) if claims else '신고 주장 입력 없음 / 가상 시험',
      '입력 근거·상태':' | '.join(evidence) if evidence else '근거 항목 없음',
      '사실 확인':' / '.join(confirmed) if confirmed else '확인된 현장 사실 자료 없음',
      '미확인':' / '.join(uncertain) if uncertain else '입력으로 특정된 미확인 사항 없음',
      '판정 기준':case.assessment or '판정 기준 별도 미입력',
      '자료 한계':' / '.join(limits) if limits else '추가 자료 한계 미판정',
      '확인 사항':'입력 근거와 실제 현장 상태 대조 필요 / 세부 항목 미정',
      '조치 종류':'미정 / 검토용 초안에서 조건부 제안',
      '법령 근거 후보/검증 전':' / '.join(map(str,case.law_references)) if case.law_references else '제공되지 않음',
      'AI 생성 가능 여부':labels.get(result.get('gate'),'상태 확인 필요'),
      '생성 가능 여부 판단 이유':' / '.join(result.get('reasons') or ['별도 제한 사유 없음']),
      'AI 모델':model_state,
      '문제 유형별 초안':draft.get('draft_template','없음') if draft else '없음 / 생성 전 또는 보류',
      '운영자 확인 메모':draft.get('review_note','없음') if draft else ' / '.join(result.get('reasons') or ['생성 결과 확인 전']),
      '최종 후보 조치 제안':'없음 / 운영자 미승인·DB 미저장',
    }
    print_ai10_detail(case.case_reference,case.issue_description or '문제 설명 없음',fields)
