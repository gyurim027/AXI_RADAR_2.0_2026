"""G-03~G-06 개발용 연동 계층. 실제 DB/인증 연결 없음.

입력 후보는 외부의 확정된 회차·구 정보에서 전달받아야 한다.
감사 기록과 변경은 한 메모리 저장소에서 원자적으로 처리한다(운영 트랜잭션 아님).
"""
from copy import deepcopy
from threading import RLock

from app.services.g03_candidate_decision import (DecisionRequest, InMemoryDecisionStore,
    G03Error, record_candidate_decision)
from app.services.g04_change_audit import ChangeRequest, prepare_change_event
from app.services.g05_previous_year_compare import compare_previous_year
from app.services.g06_round_finalize import (InMemoryFinalizeStore,
    preview_district_finalization, finalize_district, DISTRICTS)


class WorkflowError(ValueError):
    pass


class CandidateReader:
    def __init__(self, candidates):
        self.rows = {}
        for row in candidates:
            key = (row.get('run_id'), row.get('gid'))
            if (type(key[0]) is not int or key[0] <= 0 or
                not isinstance(key[1], str) or not key[1].strip() or
                row.get('gu') not in DISTRICTS or key in self.rows):
                raise WorkflowError('후보의 회차·격자·관할 또는 중복을 확인하세요.')
            self.rows[key] = deepcopy(dict(row))

    def find(self, run_id, gid):
        row = self.rows.get((run_id, gid))
        return deepcopy(row) if row is not None else None

    def for_district(self, run_id, gu):
        return [deepcopy(row) for (r, _), row in self.rows.items()
                if r == run_id and row['gu'] == gu]

    def for_run(self, run_id):
        return [deepcopy(row) for (r, _), row in self.rows.items() if r == run_id]


class ReviewWorkflow:
    def __init__(self, candidates, allowed_reason_codes):
        if not isinstance(allowed_reason_codes, set):
            raise WorkflowError('검증된 사유 코드 집합이 필요합니다.')
        self.candidates = CandidateReader(candidates)
        self.decisions = InMemoryDecisionStore()
        self.finalizations = InMemoryFinalizeStore()
        self.reason_codes = set(allowed_reason_codes)
        self.audit_events = []
        self._lock = RLock()

    def _ensure_editable(self, run_id, gu):
        if self.finalizations.round_finalized(run_id) or self.finalizations.get(run_id, gu):
            raise WorkflowError('해당 구가 이미 확정돼 결정을 변경할 수 없습니다.')

    def add_decision(self, request: DecisionRequest):
        with self._lock:
            self._ensure_editable(request.run_id, request.actor_gu)
            return record_candidate_decision(
                request=request, candidate_reader=self.candidates,
                store=self.decisions, allowed_reason_codes=self.reason_codes,
                round_is_finalized=self.finalizations.round_finalized(request.run_id))

    def change_decision(self, *, run_id, gid, actor_ref, actor_role, actor_gu,
                        new_decision, new_reason_code, new_memo, reason):
        """G-04 계획을 확인한 후 개발용 동일 저장소에 변경+이력을 함께 반영."""
        with self._lock:
            if actor_role != '구 도로관리팀' or not actor_ref or actor_gu not in DISTRICTS:
                raise WorkflowError('인증된 자기 구 도로관리팀만 변경할 수 있습니다.')
            candidate = self.candidates.find(run_id, gid)
            if candidate is None or candidate['gu'] != actor_gu:
                raise WorkflowError('자기 구의 유효한 후보만 변경할 수 있습니다.')
            self._ensure_editable(run_id, actor_gu)
            old = self.decisions.get(run_id, gid)
            if old is None:
                raise WorkflowError('최초 결정이 없어 G-04 변경을 진행할 수 없습니다.')
            if new_decision not in {'우선 점검 대상', '제외', '보류'}:
                raise WorkflowError('잘못된 결정 상태입니다.')
            if new_decision in {'제외', '보류'} and (not new_reason_code or new_reason_code not in self.reason_codes):
                raise WorkflowError('제외·보류 사유 코드가 필요합니다.')
            if new_reason_code is not None and new_reason_code not in self.reason_codes:
                raise WorkflowError('등록되지 않은 사유 코드입니다.')
            if not isinstance(new_memo, str):
                raise WorkflowError('메모는 문자열이어야 합니다.')
            # 고유번호, 관할, 최초 결정자, 가중치 버전은 변경 대상이 아님.
            before = {k: old[k] for k in ('decision', 'reason_code', 'memo')}
            after = {'decision': new_decision, 'reason_code': new_reason_code,
                     'memo': new_memo.strip()}
            plan = prepare_change_event(
                ChangeRequest(kind='후보 결정', target_ref=f'{run_id}:{gid}',
                              before=before, after=after, actor_ref=actor_ref,
                              reason=reason, round_is_finalized=False),
                observed_current=before)
            updated = {**old, **after}
            # 보호된 개발용 저장소에서 이벤트와 상태를 함께 갱신; 운영 DB 원자성 보장 아님.
            self.decisions._records[(run_id, gid)] = deepcopy(updated)
            self.audit_events.append(deepcopy(plan['audit_event']))
            return {'record': deepcopy(updated), 'audit_event': deepcopy(plan['audit_event']),
                    'storage': 'development_memory_only'}

    def compare_years(self, *, current_run_id, previous_run_id=None):
        previous = (self.decisions.list_for_run(previous_run_id)
                    if previous_run_id is not None else None)
        return compare_previous_year(
            current_run_id=current_run_id,
            current_candidates=self.candidates.for_run(current_run_id),
            previous_run_id=previous_run_id, previous_decisions=previous)

    def preview_finalize(self, run_id, gu):
        return preview_district_finalization(
            run_id=run_id, gu=gu, candidates=self.candidates.for_district(run_id, gu),
            decisions=[d for d in self.decisions.list_for_run(run_id) if d['gu'] == gu],
            store=self.finalizations)

    def finalize(self, *, run_id, gu, actor_ref, actor_role, actor_gu,
                 explicitly_confirmed, reconfirm_undecided=False):
        with self._lock:
            return finalize_district(
                run_id=run_id, gu=gu, candidates=self.candidates.for_district(run_id, gu),
                decisions=[d for d in self.decisions.list_for_run(run_id) if d['gu'] == gu],
                actor_ref=actor_ref, actor_role=actor_role, actor_gu=actor_gu,
                explicitly_confirmed=explicitly_confirmed,
                reconfirm_undecided=reconfirm_undecided, store=self.finalizations)
