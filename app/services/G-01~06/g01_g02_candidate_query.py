"""G-01 후보 목록 / G-02 격자 지도 조회. MySQL 읽기 전용.

기능정의 v0.5.3의 G-01/G-02 중 현재 SQL에 근거한 범위만 구현.
구별 열람 권한은 호출 전에 인증된 상위 서비스가 결정해야 한다.
격자 중심 좌표는 근거 지점의 실제 위치가 아니다.
"""
from __future__ import annotations

from typing import Any, Literal


class CandidateQueryError(ValueError):
    pass


BASE = """FROM priority_candidate AS p
JOIN grid_cell AS g ON p.gid = g.gid
WHERE p.run_id = %s"""
FIELDS = """p.run_id, p.gid, p.selected_yn, p.score, p.rank_no,
p.complaint_cnt, p.complaint_cnt_excl_low,
p.cond_result_yn, p.cond_hazard_yn, p.cond_exposure_yn, p.cond_vulnerable_yn,
p.matched_roles, p.note, g.gu_center, g.admin_dong_center,
g.center_lat, g.center_lon"""
SORT = {"rank": "p.rank_no", "score": "p.score", "complaints": "p.complaint_cnt"}
GU = {"수정구", "중원구", "분당구"}


def _build_conditions(*, run_id: Any, allowed_gu: set[str], gu: str | None,
                      selected_only: bool, requirement: str | None,
                      min_score: float | None) -> tuple[str, list[Any]]:
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise CandidateQueryError('정확한 회차 실행 번호(run_id)가 필요합니다.')
    if not isinstance(allowed_gu, set) or not allowed_gu or not allowed_gu.issubset(GU):
        raise CandidateQueryError('인증된 이용자의 허용 구 범위가 필요합니다.')
    if gu is not None and gu not in allowed_gu:
        raise CandidateQueryError('허용되지 않은 구 조회 요청입니다.')
    if not isinstance(selected_only, bool):
        raise CandidateQueryError('선정 여부는 참/거짓이어야 합니다.')
    if min_score is not None and (not isinstance(min_score, (float, int)) or isinstance(min_score, bool)
                                  or not 0 <= min_score <= 100):
        raise CandidateQueryError('최소 점수는 0~100 범위여야 합니다.')
    predicates = [BASE]
    params: list[Any] = [run_id]
    if gu:
        predicates.append('AND g.gu_center = %s')
        params.append(gu)
    else:
        ordered = sorted(allowed_gu)
        predicates.append('AND g.gu_center IN (' + ', '.join(['%s'] * len(ordered)) + ')')
        params.extend(ordered)
    if selected_only:
        predicates.append("AND p.selected_yn = 'Y'")
    requirements = {
        '사고 결과': 'p.cond_result_yn', '위험': 'p.cond_hazard_yn',
        '노출': 'p.cond_exposure_yn', '취약': 'p.cond_vulnerable_yn',
    }
    if requirement is not None:
        if requirement not in requirements:
            raise CandidateQueryError('지원하지 않는 우선 확인 조건입니다.')
        predicates.append('AND ' + requirements[requirement] + " = 'Y'")
    if min_score is not None:
        predicates.append('AND p.score >= %s')
        params.append(min_score)
    return '\n'.join(predicates), params


def _fetch_dicts(cursor, sql: str, params: list[Any]) -> list[dict]:
    cursor.execute(sql, tuple(params))
    names = [c[0] for c in cursor.description]
    out = []
    for row in cursor.fetchall():
        if isinstance(row, dict):
            out.append(dict(row))
        else:
            out.append(dict(zip(names, row)))
    return out


def list_candidates(cursor, *, run_id: int, allowed_gu: set[str],
                    gu: str | None = None, selected_only: bool = True,
                    requirement: str | None = None, min_score: float | None = None,
                    sort: Literal['rank', 'score', 'complaints'] = 'rank',
                    descending: bool | None = None, page: int = 1,
                    page_size: int = 30) -> dict:
    """G-01 기본 조회: 구 범위 강제, 파라미터화, 안정 정렬, 페이지 조회."""
    if sort not in SORT:
        raise CandidateQueryError('지원하지 않는 정렬 기준입니다.')
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise CandidateQueryError('페이지 번호는 1 이상 정수여야 합니다.')
    if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= 100:
        raise CandidateQueryError('페이지 크기는 1~100이어야 합니다.')
    if descending is not None and not isinstance(descending, bool):
        raise CandidateQueryError('정렬 방향이 올바르지 않습니다.')
    where, params = _build_conditions(run_id=run_id, allowed_gu=allowed_gu, gu=gu,
                                       selected_only=selected_only, requirement=requirement,
                                       min_score=min_score)
    if descending is None:
        descending = sort != 'rank'
    count_sql = 'SELECT COUNT(*) ' + where
    count_rows = _fetch_dicts(cursor, count_sql, params)
    total = int(next(iter(count_rows[0].values()))) if count_rows else 0
    direction = 'DESC' if descending else 'ASC'
    sql = f'SELECT {FIELDS}\n{where}\nORDER BY {SORT[sort]} {direction}, p.gid ASC\nLIMIT %s OFFSET %s'
    rows = _fetch_dicts(cursor, sql, [*params, page_size, (page - 1) * page_size])
    return {'items': rows, 'total': total, 'page': page, 'page_size': page_size,
            'read_only': True, 'source': 'priority_candidate + grid_cell',
            'not_included': ['결정 상태', '신뢰도 판정', '보호구역 구분', '민원 재발 구분']}


def map_candidate_grids(cursor, *, run_id: int, allowed_gu: set[str],
                        gu: str | None = None, selected_only: bool = True,
                        requirement: str | None = None, min_score: float | None = None,
                        limit: int = 2500) -> dict:
    """G-02 격자 중심 마커. 근거 위치·민원 위치 핀은 미구현/별도 출처 필요."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 2500:
        raise CandidateQueryError('지도 격자 개수는 1~2500이어야 합니다.')
    where, params = _build_conditions(run_id=run_id, allowed_gu=allowed_gu, gu=gu,
                                       selected_only=selected_only, requirement=requirement,
                                       min_score=min_score)
    sql = (f'SELECT {FIELDS}\n{where}\n'
           'AND g.center_lat IS NOT NULL AND g.center_lon IS NOT NULL\n'
           'ORDER BY p.rank_no ASC, p.gid ASC\nLIMIT %s')
    rows = _fetch_dicts(cursor, sql, [*params, limit + 1])
    if len(rows) > limit:
        raise CandidateQueryError('요청 범위의 격자가 지도 조회 한도를 넘었습니다. 구·조건을 좁혀주세요.')
    return {'grid_markers': [{'gid': x['gid'], 'lat': x['center_lat'],
                              'lon': x['center_lon'], 'score': x['score'],
                              'rank_no': x['rank_no'], 'gu': x['gu_center'],
                              'complaint_cnt': x['complaint_cnt']} for x in rows],
            'geometry': '격자 중심 좌표(격자 다각형 아님)',
            'evidence_points': None, 'complaint_points': None,
            'read_only': True, 'source': 'priority_candidate + grid_cell'}
