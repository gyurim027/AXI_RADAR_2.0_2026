"""실제 JSON, MySQL에 쓰지 않는 81번 테이블 대응 검증."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.ai10_action_template_mapping import preview_action_template_update, MappingError


def check(name, fn):
    fn()
    print('통과 | ' + name)


def reject(item, user_id=None):
    try:
        preview_action_template_update(item, user_id)
    except MappingError:
        return
    raise AssertionError('차단되어야 하는 입력이 통과했습니다.')


def base(**kw):
    d = dict(rule_id='CK-03', review_status='pending', approved=False,
             edited_template='확인 후 검토합니다.', approved_at=None)
    d.update(kw)
    return d


def main():
    def pending():
        x = preview_action_template_update(base())
        assert x['문장_검토_상태']=='초안' and x['검토자'] is None
    check('검토 대기 → 초안', pending)
    def empty_pending():
        x = preview_action_template_update(base(edited_template=None))
        assert x['조치_제안_문장'] is None and x['문장_검토_상태'] is None
        assert x['검토_일시'] is None
    check('문장 없는 검토 대기 → 문장·검토 상태 모두 NULL', empty_pending)
    def whitespace_pending():
        x = preview_action_template_update(base(edited_template='  '))
        assert x['조치_제안_문장'] is None and x['문장_검토_상태'] is None
    check('공백 문장 → 문장·검토 상태 모두 NULL', whitespace_pending)
    def approved():
        x = preview_action_template_update(base(review_status='approved', approved=True,
                 approved_at='2026-10-19T03:30:15+00:00'), 3)
        assert x['문장_검토_상태']=='검토 완료' and x['검토자']==3
        assert x['검토_일시']=='2026-10-19 03:30:15'
    check('승인 → 검토 완료 (운영자 번호, UTC 시각)', approved)
    check('반려를 임의로 초안 처리하지 않음', lambda: reject(base(review_status='rejected')))
    check('상태·승인 모순 차단', lambda: reject(base(approved=True)))
    check('빈 승인 문장 차단', lambda: reject(base(review_status='approved',approved=True,edited_template=' ',approved_at='2026-10-19T03:30:15+00:00'),3))
    check('검토자 문자 식별값 차단', lambda: reject(base(review_status='approved',approved=True,approved_at='2026-10-19T03:30:15+00:00'),'AI10_TEST'))
    check('운영자 번호 없이 승인 저장 차단', lambda: reject(base(review_status='approved',approved=True,approved_at='2026-10-19T03:30:15+00:00')))
    check('시간대 없는 승인 시각 차단', lambda: reject(base(review_status='approved',approved=True,approved_at='2026-10-19T03:30:15'),3))
    check('미승인과 승인 시각 모순 차단', lambda: reject(base(approved_at='2026-10-19T03:30:15+00:00')))
    check('잘못된 CK 차단', lambda: reject(base(rule_id='abc')))
    def limited_columns():
        x = preview_action_template_update(base(events=[{'action':'edited'}],revision=2,findings=[1]))
        assert set(x) == {'항목ID','조치_제안_문장','문장_검토_상태','검토자','검토_일시'}
    check('상세 이력·경고를 DB 컬럼으로 임의 생성하지 않음',limited_columns)
    def immutable():
        d=base();snapshot=repr(d);preview_action_template_update(d);assert repr(d)==snapshot
    check('입력 데이터 변경 없음',immutable)
    print('결과: 14/14 통과 | SQL/JSON/DB 변경 없음')

if __name__=='__main__':
    main()
