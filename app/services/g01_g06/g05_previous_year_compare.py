"""G-05: 작년 G-03 결정과 올해 우선 점검 후보를 나란히 비교.

기능정의 v0.5.3, G-05: 올해 후보, 작년 결정·사유, 제외/보류 재등장.
각 연도의 run_id는 상위 기능이 지정한다. 운영 DB 접근·기록·AI 호출 없음.
"""
from __future__ import annotations
from typing import Iterable, Mapping

DECISIONS = frozenset({'우선 점검 대상', '제외', '보류'})

class G05Error(ValueError):
    pass


def compare_previous_year(*, current_run_id: int, current_candidates: Iterable[Mapping],
                          previous_run_id: int | None = None,
                          previous_decisions: Iterable[Mapping] | None = None) -> list[dict]:
    """올해 후보 기준으로 반환. 작년 자료가 없으면 임의로 결정·사유를 채우지 않음.

    연도별 회차 식별자와 전년도 자료는 호출자가 확정해 전달한다.
    `gid`는 같은 격자 체계 안에서 비교된다는 전제를 상위에서 보장해야 한다.
    """
    if type(current_run_id) is not int or current_run_id <= 0:
        raise G05Error('올해 회차 번호가 필요합니다.')
    if (previous_run_id is None) != (previous_decisions is None):
        raise G05Error('지난 회차 번호와 결정 기록은 함께 제공해야 합니다.')
    if previous_run_id is not None and (type(previous_run_id) is not int or previous_run_id <= 0 or previous_run_id == current_run_id):
        raise G05Error('서로 다른 유효한 회차 번호가 필요합니다.')
    prev_by_gid: dict[str, Mapping] = {}
    if previous_decisions is not None:
        for old in previous_decisions:
            gid = old.get('gid')
            if old.get('run_id') != previous_run_id or not isinstance(gid, str) or not gid.strip():
                raise G05Error('지난 회차 결정 기록의 회차·격자 번호를 확인하세요.')
            if gid in prev_by_gid:
                raise G05Error('지난 회차에 같은 격자의 결정 기록이 중복되었습니다.')
            if old.get('decision') not in DECISIONS:
                raise G05Error('지난 회차의 결정값을 확인하세요.')
            if old['decision'] in {'제외', '보류'} and not str(old.get('reason_code') or '').strip():
                raise G05Error('지난 회차 제외·보류 사유가 누락되었습니다.')
            prev_by_gid[gid] = old
    seen: set[str] = set()
    output = []
    for candidate in current_candidates:
        gid = candidate.get('gid')
        if candidate.get('run_id') != current_run_id or not isinstance(gid, str) or not gid.strip():
            raise G05Error('올해 후보의 회차·격자 번호를 확인하세요.')
        if gid in seen:
            raise G05Error('올해 후보 격자 번호가 중복되었습니다.')
        seen.add(gid)
        old = prev_by_gid.get(gid)
        output.append({
            'run_id': current_run_id,
            'gid': gid,
            'current_score': candidate.get('score'),
            'current_rank_no': candidate.get('rank_no'),
            'previous_run_id': previous_run_id,
            'previous_decision': old['decision'] if old else None,
            'previous_reason_code': old.get('reason_code') if old else None,
            'previous_memo': old.get('memo') if old else None,
            'previous_decided_at': old.get('decided_at') if old else None,
            'previous_comparison_status': '전년도 결정 있음' if old else '비교 자료 없음',
            'returned_after_exclusion_or_hold': bool(old and old['decision'] in {'제외', '보류'}),
        })
    return output
