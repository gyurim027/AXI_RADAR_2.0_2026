"""G-06 구별 점검 대상 확정 및 3개 구 회차 확정 (개발용 메모리 상태).

기능정의서 v0.5.3 / 03_상세기능목록 G-06:
- 도로관리팀 자기 구 결정 완료 후 우선 점검 대상 확정
- 확정 전 우선점검/제외·보류/미결정 건수 표시, 미결정 존재 시 재확인
- 3개 구 모두 확정하면 회차 확정 및 산정 조건 기록서 연계 필요
운영 인증·DB 트랜잭션·산정 조건 기록서 작성은 미연동. 기존 DB 변경 없음.
"""
from __future__ import annotations
from copy import deepcopy

DISTRICTS = frozenset({'수정구', '중원구', '분당구'})
DECISIONS = frozenset({'우선 점검 대상', '제외', '보류'})

class G06Error(ValueError):
    pass

class InMemoryFinalizeStore:
    def __init__(self):
        self._districts = {}
        self._final_rounds = set()

    def get(self, run_id, gu):
        record = self._districts.get((run_id, gu))
        return deepcopy(record) if record else None

    def list_run(self, run_id):
        return {gu: self.get(run_id, gu) for gu in DISTRICTS}

    def save(self, record):
        key = (record['run_id'], record['gu'])
        if key in self._districts:
            raise G06Error('이미 확정된 구입니다.')
        self._districts[key] = deepcopy(record)
        if all((record['run_id'], gu) in self._districts for gu in DISTRICTS):
            self._final_rounds.add(record['run_id'])

    def round_finalized(self, run_id):
        return run_id in self._final_rounds


def _validate(run_id, gu, candidates, decisions):
    if type(run_id) is not int or run_id <= 0 or gu not in DISTRICTS:
        raise G06Error('올바른 회차 실행 번호·관할 구가 필요합니다.')
    if not isinstance(candidates, list) or not isinstance(decisions, list):
        raise G06Error('후보·결정 기록 목록이 필요합니다.')
    ids = set()
    for c in candidates:
        if c.get('run_id') != run_id or c.get('gu') != gu or not isinstance(c.get('gid'), str) or not c['gid'].strip():
            raise G06Error('회차·구가 다른 후보 또는 잘못된 격자가 포함됐습니다.')
        if c['gid'] in ids:
            raise G06Error('후보가 중복됐습니다.')
        ids.add(c['gid'])
    by_id = {}
    for d in decisions:
        gid = d.get('gid')
        if d.get('run_id') != run_id or d.get('gu') != gu or gid not in ids or gid in by_id or d.get('decision') not in DECISIONS:
            raise G06Error('결정 목록의 회차·구·상태·중복을 확인하세요.')
        by_id[gid] = d
    counts = {state: sum(x['decision'] == state for x in by_id.values()) for state in DECISIONS}
    return {
        'run_id': run_id, 'gu': gu, 'total_candidates': len(ids),
        'selected_count': counts['우선 점검 대상'],
        'excluded_count': counts['제외'], 'held_count': counts['보류'],
        'undecided_count': len(ids)-len(by_id),
        'undecided_gids': sorted(ids-by_id.keys()),
        'requires_reconfirmation': len(ids) != len(by_id),
    }


def preview_district_finalization(*, run_id, gu, candidates, decisions, store):
    summary = _validate(run_id, gu, candidates, decisions)
    if store.get(run_id, gu):
        raise G06Error('이미 확정된 구입니다. 기존 결정은 G-04 변경 기록 대상으로 검토해야 합니다.')
    return summary


def finalize_district(*, run_id, gu, candidates, decisions, actor_role,
                      actor_gu, actor_ref, explicitly_confirmed,
                      reconfirm_undecided=False, store):
    summary = preview_district_finalization(run_id=run_id, gu=gu, candidates=candidates, decisions=decisions, store=store)
    if actor_role != '구 도로관리팀' or actor_gu != gu or not isinstance(actor_ref, str) or not actor_ref.strip():
        raise G06Error('인증된 자기 구 도로관리팀의 확정 요청만 허용합니다.')
    if explicitly_confirmed is not True:
        raise G06Error('구별 우선 점검 대상 확정 확인이 필요합니다.')
    if summary['requires_reconfirmation'] and reconfirm_undecided is not True:
        raise G06Error(f"미결정 후보 {summary['undecided_count']}건 재확인이 필요합니다.")
    record = {**summary, 'actor_ref': actor_ref.strip(), 'district_finalized': True,
              'storage': '개발용 메모리 / 운영 DB 미저장'}
    store.save(record)
    states = store.list_run(run_id)
    return {**deepcopy(record), 'finalized_districts': sorted(g for g,v in states.items() if v),
            'round_finalized': store.round_finalized(run_id),
            'calculation_conditions_record': '연결 대기 / 실제 기록서 미생성'}
