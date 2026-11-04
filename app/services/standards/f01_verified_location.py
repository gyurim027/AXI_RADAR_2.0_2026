"""Read-only, cautious F-01 district corroboration from already verified source ID.

A source's own reported gu is not a spatial boundary proof. Use it only for
ADVISORY routing when it agrees with the grid's center-gu and the original
source has a first-hand position. Do not use caller-supplied gu, inferred
addresses, or the center-gu alone. No F-02 conditional branch is waived.
"""
from __future__ import annotations
from app.core import db

BOROUGHS = frozenset({'수정구', '중원구', '분당구'})


def verified_advisory_gu(row: dict, *, gid: str, table: str) -> dict:
    """Return advisory district only when two DB-stored signals agree.

    This is NOT a verified point-in-polygon determination; grid cells can
    overlap district boundaries. District-specific contacts remain advisory.
    """
    result = {'gu': None, 'status': '확인 필요', 'reason': 'SOURCE_LOCATION_NOT_CONFIRMED'}
    source_gu = str(row.get('gu') or '').strip()
    if source_gu not in BOROUGHS:
        result['reason'] = 'SOURCE_GU_MISSING_OR_UNKNOWN'
        return result
    if table != 'src_complaint':
        result['reason'] = 'SOURCE_POSITION_PRECISION_UNVERIFIED'
        return result
    if str(row.get('coord_accuracy') or '').strip() != '원본 좌표':
        result['reason'] = 'SOURCE_COORD_ACCURACY_UNVERIFIED'
        return result
    if not str(row.get('coord_method') or '').strip().startswith('원본 좌표'):
        result['reason'] = 'SOURCE_COORD_METHOD_UNVERIFIED'
        return result
    try:
        lat = float(row.get('lat'))
        lon = float(row.get('lon'))
        if not (37.0 < lat < 38.0 and 126.0 < lon < 128.0):
            raise ValueError('NOT_SEONGNAM_COORD')
    except (TypeError, ValueError):
        result['reason'] = 'SOURCE_COORD_MISSING_OR_INVALID'
        return result
    rows = db.read_only('SELECT gu_center FROM grid_cell WHERE gid = %s LIMIT 2', (gid,))
    if len(rows) != 1:
        result['reason'] = 'GRID_ID_MISSING_OR_NONUNIQUE'
        return result
    grid_gu = str(rows[0].get('gu_center') or '').strip()
    if grid_gu != source_gu:
        result['reason'] = 'SOURCE_GU_GRID_CENTER_MISMATCH'
        return result
    return {'gu': source_gu, 'status': '격자 중심구 교차확인',
            'reason': 'ORIGINAL_SOURCE_COORD_AND_GU_AGREE_WITH_GRID_CENTER',
            'warning': '격자 중심구는 지점의 행정구역 경계 판정과 다릅니다. 최종 관할 미확정'}
