"""G-03 후보별 사람의 결정 기록 — 독립 도메인 서비스.

기능정의 v0.5.3: 우선 점검 대상/제외/보류, 사유 선택과 메모,
도로관리팀 자기 구 제한, 회차와 가중치 버전 기록.
운영 인증·사유 목록·영구 저장소·G-04 변경이력은 미연결.

주의: priority_candidate.selected_yn은 산정엔진의 후보 선정 값이며 G-03 사람의
결정 값이 아니다. 기존 decision.decision_type도 G-03 상태와 의미가 다르다.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Protocol

GU = frozenset({'수정구', '중원구', '분당구'})
DECISIONS = frozenset({'우선 점검 대상', '제외', '보류'})


class G03Error(ValueError):
    pass


class CandidateReader(Protocol):
    def find(self, run_id: int, gid: str) -> dict | None: ...


class DecisionStore(Protocol):
    def get(self, run_id: int, gid: str) -> dict | None: ...
    def add(self, record: dict) -> None: ...


@dataclass(frozen=True)
class DecisionRequest:
    run_id: int
    gid: str
    decision: str
    reason_code: str | None
    memo: str
    weight_version: str
    actor_ref: str
    actor_role: str
    actor_gu: str


def record_candidate_decision(*, request: DecisionRequest,
                              candidate_reader: CandidateReader,
                              store: DecisionStore,
                              allowed_reason_codes: set[str],
                              round_is_finalized: bool = False) -> dict:
    """인증·회차 확정상태·사유목록은 상위 기능에서 검증해 전달할 입력.

    전달된 역할/구 정보가 실제 인증값인지 이 함수만으로 증명할 수 없음.
    동시 저장 경쟁은 운영 저장소의 유일 제약/트랜잭션으로 별도 처리 필요.
    """
    q = request
    if not isinstance(q.run_id, int) or isinstance(q.run_id, bool) or q.run_id <= 0:
        raise G03Error('정확한 회차 실행 번호가 필요합니다.')
    if not isinstance(q.gid, str) or not q.gid.strip():
        raise G03Error('후보 격자 번호가 필요합니다.')
    if q.actor_role != '구 도로관리팀' or q.actor_gu not in GU:
        raise G03Error('구 도로관리팀만 자기 구 후보에 결정을 기록할 수 있습니다.')
    if not isinstance(q.actor_ref, str) or not q.actor_ref.strip():
        raise G03Error('인증된 결정자 식별값이 필요합니다.')
    if not isinstance(round_is_finalized, bool):
        raise G03Error('회차 확정 여부가 필요합니다.')
    if round_is_finalized:
        raise G03Error('확정된 회차의 결정은 이 기능에서 덮어쓸 수 없습니다.')
    if q.decision not in DECISIONS:
        raise G03Error('지원하지 않는 결정입니다.')
    if not isinstance(q.weight_version, str) or not q.weight_version.strip():
        raise G03Error('해당 회차의 가중치 버전을 전달받아야 합니다.')
    if not isinstance(q.memo, str):
        raise G03Error('메모 형식이 올바르지 않습니다.')
    if not isinstance(allowed_reason_codes, set):
        raise G03Error('확정된 사유 목록이 필요합니다.')
    if q.decision in {'제외', '보류'}:
        if not isinstance(q.reason_code, str) or not q.reason_code.strip():
            raise G03Error('제외 또는 보류는 사유를 선택해야 합니다.')
        if q.reason_code not in allowed_reason_codes:
            raise G03Error('사유 목록에 없는 선택값입니다.')
    elif q.reason_code is not None and q.reason_code not in allowed_reason_codes:
        raise G03Error('사유 목록에 없는 선택값입니다.')
    candidate = candidate_reader.find(q.run_id, q.gid)
    if not candidate or candidate.get('run_id') != q.run_id or candidate.get('gid') != q.gid:
        raise G03Error('해당 회차의 후보가 아닙니다.')
    if candidate.get('gu') != q.actor_gu:
        raise G03Error('자기 구가 아닌 후보는 결정할 수 없습니다.')
    if store.get(q.run_id, q.gid) is not None:
        raise G03Error('기존 결정이 있습니다. 변경은 G-04 변경 이력 정책과 연결 후 처리해야 합니다.')
    rec = {
        'run_id': q.run_id, 'gid': q.gid, 'gu': q.actor_gu,
        'decision': q.decision, 'reason_code': q.reason_code,
        'memo': q.memo.strip(), 'weight_version': q.weight_version.strip(),
        'actor_ref': q.actor_ref.strip(),
        'decided_at': datetime.now(timezone.utc).isoformat(),
        'storage': 'development_store_only',
    }
    store.add(rec)
    return dict(rec)


class InMemoryDecisionStore:
    """개발용 저장소: 재시작 시 소멸. 운영 DB/원본 데이터를 수정하지 않음."""
    def __init__(self):
        self._records: dict[tuple[int, str], dict] = {}

    def get(self, run_id: int, gid: str) -> dict | None:
        value = self._records.get((run_id, gid))
        return dict(value) if value else None

    def add(self, record: dict) -> None:
        key = (record['run_id'], record['gid'])
        if key in self._records:
            raise G03Error('이미 기록된 후보 결정입니다.')
        self._records[key] = dict(record)

    def list_for_run(self, run_id: int) -> list[dict]:
        return [dict(x) for (r, _), x in self._records.items() if r == run_id]
