"""AI-10 81 -> H-06 -> 82 독립 연결 시험. 실제 DB/개발용 JSON 변경 없음."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ai10_action_template_mapping import preview_action_template_update
from app.services.ai10_action_proposal import compose_action_proposal
from app.services.ai10_candidate_action_mapping import (
    CandidateActionMappingError, preview_candidate_action_row,
)


def main():
    n = 0
    def check(name, condition):
        nonlocal n
        assert condition, name
        n += 1
        print('통과 | ' + name)

    approved = {
        'rule_id': 'CK-03', 'edited_template': '점자블록의 연속성을 현장에서 확인하고 조치를 검토합니다.',
        'review_status': 'approved', 'approved': True,
        'reviewer': 'AI10_TEST', 'approved_at': '2026-10-19T03:30:15+00:00',
        'revision': 1, 'events': [{'action': 'approve'}], 'findings': [],
    }
    pending = {
        **approved, 'rule_id': 'CK-04', 'review_status': 'pending',
        'approved': False, 'approved_at': None,
    }
    with tempfile.TemporaryDirectory(prefix='ai10_flow_') as work:
        store = Path(work) / 'review.json'
        store.write_text(json.dumps({'items': {'CK-03': approved, 'CK-04': pending}}, ensure_ascii=False), encoding='utf-8')
        before = store.read_bytes()

        row81 = preview_action_template_update(approved, reviewer_user_id=3)
        check('81번 CK 연결', row81['항목ID'] == 'CK-03')
        check('81번 검토 완료 상태', row81['문장_검토_상태'] == '검토 완료')
        check('81번 승인 문장 보존', row81['조치_제안_문장'] == approved['edited_template'])
        check('81번 검토자 형식·시각', row81['검토자'] == 3 and row81['검토_일시'] == '2026-10-19 03:30:15')

        proposal = compose_action_proposal('CK-03', confirmed_department='시험 부서',
                                           confirmed_legal_basis='시험 조문', store=store)
        check('H-06 승인 문장만 구성', proposal is not None and proposal['action_proposal_sentence'] == row81['조치_제안_문장'])
        check('H-06 전달값 유지', proposal['receiving_department'] == '시험 부서' and proposal['confirmed_legal_basis'] == '시험 조문')

        row82 = preview_candidate_action_row(proposal, run_id=7, gid='GRID-001', selected_yn='Y', item_id='CK-03')
        check('82번 후보·CK 식별값 유지', (row82['run_id'], row82['gid'], row82['item_id']) == (7, 'GRID-001', 'CK-03'))
        check('82번 조치 문장·부서·조문 유지', (row82['action_text'], row82['dept_text'], row82['basis_text']) ==
              (approved['edited_template'], '시험 부서', '시험 조문'))

        check('미승인 CK 조치 제안 차단', compose_action_proposal('CK-04', confirmed_department='시험 부서',
                                         confirmed_legal_basis='시험 조문', store=store) is None)
        try:
            preview_candidate_action_row(proposal, run_id=7, gid='GRID-001', selected_yn='N', item_id='CK-03')
        except CandidateActionMappingError:
            check('미선정 후보 82번 저장값 생성 차단', True)
        else:
            check('미선정 후보 82번 저장값 생성 차단', False)
        check('실제 저장소 아닌 임시 파일만 읽고 원본 불변', store.read_bytes() == before)

    print(f'결과: {n}/11 통과 | 실제 JSON/SQL/DB 변경 없음')


if __name__ == '__main__':
    main()
