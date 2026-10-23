"""SQL 82번 컬럼 대응 검증. DB 접속 및 실제 파일 수정 없음."""
from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.ai10_candidate_action_mapping import (  # noqa: E402
    CandidateActionMappingError, preview_candidate_action_row,
)


def main():
    count = 0
    good = {
        'rule_id': 'CK-03',
        'action_proposal_sentence': '점자블록 연속성을 확인하고 설치 요청 필요성을 검토할 수 있습니다.',
        'receiving_department': '시험 확인 부서',
        'confirmed_legal_basis': '시험 확인 조문',
        'missing_information': [],
        'ready_for_full_display': True,
        'revision': 2, 'approved_at': 'TEST',
    }
    args = dict(run_id=7, gid='GRID-001', selected_yn='Y', item_id='CK-03')

    def ok(name, expr):
        nonlocal count
        assert expr, name
        count += 1
        print('통과 | ' + name)

    def denied(name, proposal=good, **changes):
        call = {**args, **changes}
        try:
            preview_candidate_action_row(proposal, **call)
        except CandidateActionMappingError:
            ok(name, True)
        else:
            ok(name, False)

    snapshot = deepcopy(good)
    row = preview_candidate_action_row(good, **args)
    ok('82번 컬럼 6개만 반환', set(row) == {'run_id','gid','item_id','action_text','dept_text','basis_text'})
    ok('78번 후보 키 유지', row['run_id'] == 7 and row['gid'] == 'GRID-001')
    ok('81번 CK 번호 유지', row['item_id'] == 'CK-03')
    ok('조치 문장·부서·조문 그대로 전달', row['action_text'] == good['action_proposal_sentence'] and row['dept_text'] == good['receiving_department'] and row['basis_text'] == good['confirmed_legal_basis'])
    denied('미선정 격자 사용 차단', selected_yn='N')
    denied('실행 번호 형식 오류 차단', run_id='7')
    denied('격자 번호 누락 차단', gid='')
    denied('격자 번호 길이 초과 차단', gid='X'*33)
    denied('CK 항목 불일치 차단', item_id='CK-04')
    denied('승인된 결과 없음 차단', proposal=None)
    denied('누락 정보가 있는 결과 차단', proposal={**good, 'missing_information':['받는 부서']})
    denied('표시 준비되지 않은 결과 차단', proposal={**good, 'ready_for_full_display':False})
    denied('빈 조치 문장 차단', proposal={**good, 'action_proposal_sentence':' '})
    denied('부서 정보 누락 차단', proposal={**good, 'receiving_department':None})
    denied('근거 조문 누락 차단', proposal={**good, 'confirmed_legal_basis':None})
    ok('원본 응답 변경 없음', good == snapshot)
    print(f'결과: {count}/{count} 통과 | SQL/JSON/DB 변경 없음')


if __name__ == '__main__':
    main()
