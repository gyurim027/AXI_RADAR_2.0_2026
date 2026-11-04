"""79번 민원 적재 명세 v1.1 → CK 경계 검사. Gemini·DB 미호출."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.ai10_h06_ck_correspondence import inspect_complaint_handoff


def main():
    count = 0
    def check(desc, condition):
        nonlocal count
        assert condition, desc
        count += 1
        print('PASS | ' + desc)
    check('입력 없음', inspect_complaint_handoff(None)['status'] == '입력 부족')
    blank = {'가린_요약': None, '관련_여부': None, '보행_유형': None, '분류_신뢰도': None, '판단근거': None,
             '반복_제목': '같은 제목 30건', '중복_표시': '같은 행 3건', '민원제목': '비공개원문'}
    status = inspect_complaint_handoff(blank)
    check('초기 적재의 AI-01 NULL 감지', status['status'] == 'AI-01 결과 미완료 또는 누락')
    check('초기 적재에서 CK 후보 생성 안 함', status['ck_candidates'] == [])
    check('반복 제목만으로 CK-14 생성 안 함', 'CK-14' not in str(status))
    ready = {'가린_요약': '가림 요약', '관련_여부': '관련', '보행_유형': '보도',
             '분류_신뢰도': 0.91, '판단근거': '분류 근거', '반복_제목': '같은 제목 30건'}
    result = inspect_complaint_handoff(ready)
    check('AI-01 결과 입력 상태 표시', result['status'].startswith('AI-01 결과 입력됨'))
    check('AI-01 분류 결과를 CK로 변환하지 않음', result['ck_candidates'] == [])
    check('입력 원문이 결과에 노출되지 않음', '비공개원문' not in str(result))
    check('빈 문자열도 미입력으로 취급', '보행_유형' in inspect_complaint_handoff({**ready,'보행_유형':'  '})['missing_fields'])
    print(f'결과: {count}/{count} 통과 | API/DB 미호출')
if __name__ == '__main__': main()
