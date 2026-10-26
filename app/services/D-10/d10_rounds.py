"""D-10 회차 생성 및 열기 규칙. 개발용 메모리 저장소; 운영 DB 미연결.

기능정의서 v0.5.3: 회차 생성 시 '산정 중', 산정 완료 후 연간은
'검토 중', 반기 참고는 '참고'. 누락 자료는 고지하되 열기 차단 조건 아님.
G-06 최종 확정 및 사용자 알림은 이 모듈의 책임이 아님.
"""
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

Kind = Literal['연간', '반기 참고']
Status = Literal['산정 중', '검토 중', '참고']


class RoundError(ValueError):
    pass


@dataclass
class Round:
    temporary_id: str
    name: str
    kind: Kind
    state: Status = '산정 중'
    missing_sources: list[str] = field(default_factory=list)
    unevaluated_areas: list[str] = field(default_factory=list)

    def as_dict(self):
        return {
            'temporary_id': self.temporary_id,
            'name': self.name,
            'kind': self.kind,
            'state': self.state,
            'missing_sources': list(self.missing_sources),
            'unevaluated_areas': list(self.unevaluated_areas),
            'storage': '개발용 메모리 / 운영 DB 미저장',
        }


class RoundStore:
    def __init__(self):
        self._rounds: dict[str, Round] = {}

    def create(self, name: str, kind: Kind) -> dict:
        if kind not in ('연간', '반기 참고'):
            raise RoundError('회차 종류는 연간 또는 반기 참고여야 합니다.')
        if not isinstance(name, str) or not name.strip():
            raise RoundError('회차 이름은 필수입니다.')
        entry = Round(temporary_id='DEV-ROUND-'+uuid4().hex[:12], name=name.strip(), kind=kind)
        self._rounds[entry.temporary_id] = entry
        return entry.as_dict()

    def get(self, temporary_id: str) -> dict:
        if temporary_id not in self._rounds:
            raise RoundError('회차를 찾을 수 없습니다.')
        return self._rounds[temporary_id].as_dict()

    def list_all(self) -> list[dict]:
        return [r.as_dict() for r in self._rounds.values()]

    def preview_open(self, temporary_id: str, *, calculation_completed: bool,
                     missing_sources: list[str] | None = None,
                     unevaluated_areas: list[str] | None = None) -> dict:
        r = self._must_get(temporary_id)
        if r.state != '산정 중':
            raise RoundError('이미 열린 회차입니다.')
        if not isinstance(calculation_completed, bool):
            raise RoundError('산정 완료 확인값이 필요합니다.')
        missing = self._clean(missing_sources)
        unevaluated = self._clean(unevaluated_areas)
        return {
            'temporary_id': temporary_id,
            'current_state': r.state,
            'next_state': '검토 중' if r.kind == '연간' else '참고',
            'can_open': calculation_completed,
            'reason': '산정 완료 확인 필요' if not calculation_completed else '열기 가능',
            'missing_sources': missing,
            'unevaluated_areas': unevaluated,
            'warning': '누락 자료·미평가 분야는 표시하되 산정 완료 시 열기를 막지 않습니다.',
            'calculation_evidence_source': '상위 산정 기능에서 검증 후 전달받아야 함 / 현재 미연동',
        }

    def open(self, temporary_id: str, *, calculation_completed: bool,
             missing_sources: list[str] | None = None,
             unevaluated_areas: list[str] | None = None) -> dict:
        preview = self.preview_open(
            temporary_id, calculation_completed=calculation_completed,
            missing_sources=missing_sources, unevaluated_areas=unevaluated_areas,
        )
        if not preview['can_open']:
            raise RoundError('산정이 끝나지 않아 회차를 열 수 없습니다.')
        entry = self._must_get(temporary_id)
        entry.state = preview['next_state']
        entry.missing_sources = preview['missing_sources']
        entry.unevaluated_areas = preview['unevaluated_areas']
        return entry.as_dict()

    def _must_get(self, key: str) -> Round:
        if key not in self._rounds:
            raise RoundError('회차를 찾을 수 없습니다.')
        return self._rounds[key]

    @staticmethod
    def _clean(values: list[str] | None) -> list[str]:
        if values is None:
            return []
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise RoundError('누락 자료·미평가 분야는 문자열 목록이어야 합니다.')
        return list(dict.fromkeys(v.strip() for v in values if v.strip()))
