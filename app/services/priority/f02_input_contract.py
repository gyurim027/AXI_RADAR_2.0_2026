"""Pure F-02 road classification input validation (NOT a source-of-truth loader).

Data from a verified provider must supply explicit row provenance. Do not
turn the 2026-10-27 preliminary CSV into an operational ground truth.
"""
from __future__ import annotations
from typing import Any, Mapping


def validate_f02_record(candidate_gid: str, record: Mapping[str, Any] | None) -> dict:
    """Validate traceability and status, not the road jurisdiction itself."""
    out = {'gid': candidate_gid, 'roadType': None, 'f02Status': '확인 필요',
           'f02EvidenceRef': None, 'f02Reason': '검증된 F-02 입력이 없습니다.'}
    if not isinstance(record, Mapping):
        return out
    gid = record.get('gid')
    status = record.get('판정')
    road = record.get('도로 종류')
    source = record.get('표')
    key = record.get('행 키')
    if gid != candidate_gid:
        out['f02Reason'] = 'F-02 격자 연결 키가 일치하지 않습니다.'
        return out
    if status != '연결' or not isinstance(road, str) or not road.strip():
        out['f02Reason'] = '도로 종류를 확정할 수 있는 F-02 판정이 아닙니다.'
        return out
    if not all(isinstance(v, str) and v.strip() for v in (source, key)):
        out['f02Reason'] = 'F-02 원천 테이블과 행 식별값이 없습니다.'
        return out
    # Even a linked record is preliminary until owner confirms it as current.
    if record.get('sourceVerified') is not True:
        out['f02Reason'] = 'F-02 원천의 현재성·확인 상태가 검증되지 않았습니다.'
        return out
    out.update(roadType=road.strip(), f02Status='확인됨',
               f02EvidenceRef=f'{source.strip()}::{key.strip()}',
               f02Reason='원천 검증된 F-02 도로 종류 판정 결과')
    return out
