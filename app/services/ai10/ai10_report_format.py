"""AI-10 개별 사례 표시 전용. 판정/승인 변경 없이 기존 SAMPLE 상세 형식을 유지한다."""

def show_case(*, identity, claim, verification, unverified, link, rule=None,
              gemini='미호출', draft='미생성 / Gemini 호출 전', note='확인된 운영자 메모 없음',
              final='없음 / CK 확정·운영자 승인·대상 값 연결 전', extra=None):
    print('=' * 65)
    print(identity)
    print(f'[신고인의 주장] {claim}')
    print(f'[사실 확인] {verification}')
    print(f'[미확인] {unverified}')
    print(f'[연결] {link}')
    for label, value in (extra or []):
        print(f'[{label}] {value}')
    if rule:
        print(f"[CK 판정 기준] {rule.get('judgment_type') or '기준표 항목 미제공'}")
        print(f"[CK 자료 한계] {rule.get('data_limitation') or '기준표 항목 미제공'}")
        print(f"[CK 확인 사항] {rule.get('check_required') or '기준표 항목 미제공'}")
        print(f"[CK 조치 종류] {rule.get('action_type') or '기준표 항목 미제공'}")
        print(f"[법령 근거 후보/검증 전] {rule.get('legal_reference_candidate') or '없음'}")
    else:
        print('[CK 판정 기준] CK 기준표 연결 없음')
        print('[CK 자료 한계] 기준표 미연결 또는 CK 후보 없음')
        print('[CK 확인 사항] 상위 판정 결과 또는 기준표 연결 필요')
        print('[CK 조치 종류] 미정')
        print('[법령 근거 후보/검증 전] 없음')
    print()
    print(f'[Gemini] {gemini}')
    print(f'[CK 유형별 초안] {draft}')
    print(f'[운영자 확인 메모] {note}')
    print(f'[최종 후보 조치 제안] {final}')


def show_draft_two_lines(text):
    """원문 그대로 표시하되, 문장 경계의 공백만 줄바꿈으로 표현한다."""
    import re
    parts = re.split(r'(?<=[.!?])\s+', str(text).strip(), maxsplit=1)
    print(f'[CK 유형별 초안] {parts[0]}')
    if len(parts) > 1:
        print(f'                {parts[1]}')
