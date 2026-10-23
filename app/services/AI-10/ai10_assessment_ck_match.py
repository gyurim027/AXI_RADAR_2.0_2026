"""07~10번 판정 CSV의 *기록값*으로 05_03 CK 검토 후보를 찾는다.

후보 ≠ 확인된 위험 ≠ 확정 CK. 원문, 이미지, Gemini, DB는 사용하지 않는다.
공식 기준표의 2026-10-19 버전 및 CSV v1.10의 필드·값만 취급한다.
"""
from __future__ import annotations
from typing import Any
from .ai10_h06_ck_correspondence import validate_external_ck

TABLES = {'07_assess_crosswalk','08_assess_sidewalk','09_assess_intersection','10_assess_zone'}


def _is(row: dict[str, Any], key: str, values: set[str]) -> bool:
    return str(row.get(key) or '').strip() in values


def match_assessment_ck(table: str, row: dict[str, Any] | None) -> dict[str, Any]:
    """외부 판정 결과 한 행을 후보 목록으로 대조. 승인/확정/저장 절대 수행하지 않음."""
    if table not in TABLES or not isinstance(row, dict):
        return {'status':'입력 부족','ck_candidates':[], 'detail':'지원하는 07~10번 테이블과 판정 행이 필요합니다.'}
    matches: list[tuple[str,str,str]] = []

    def add(ck: str, field: str, caution: str):
        if validate_external_ck(ck)['status'] == '식별자 확인':
            matches.append((ck, field, caution))

    if table == '07_assess_crosswalk':
        if _is(row,'안내_점자블록_원본',{'N'}):
            add('CK-03','안내_점자블록_원본','원본 등록값이며 현재 점자블록 부재 확정이 아님')
        if _is(row,'조도_비교_결과(기준: 표 5.1 수평면 최소 6 lx)',{'최소 수평조도 6 미만 측정점 있음'}):
            add('CK-05','조도_비교_결과(기준: 표 5.1 수평면 최소 6 lx)','측정점 기준 비교이며 실제 조명 보강 필요 확정이 아님')
        if _is(row,'신호_점검_결과',{
            '판단 불가 — 연결된 신호등 없음','판단 불가 — 최대 시간은 충분하나 실제 보행 녹색시간은 모름',
            '부족 가능성 높음 — 건널 수 있는 최대 시간도 필요 시간보다 짧음',
            '부족 가능성 높음 — 경찰서 신호값: 어느 보행 현시도 필요 시간보다 짧음',
            '현시마다 다름 — 이 횡단보도가 어느 현시인지 확인 필요 (경찰서 신호값)'}):
            add('CK-09','신호_점검_결과','신호시간 부족 확정이 아니라 현시·신호자료 확인 대상')
        if _is(row,'NG_중간대피_판정',{'4~7차로·중간 대피 공간 없음','8차로 이상(편도 4차로 이상 추정)·중간 대피 공간 없음'}):
            add('CK-12','NG_중간대피_판정','도면·원본 기준이며 현장 대피공간 설치 판단은 별도')
    elif table == '08_assess_sidewalk':
        if _is(row,'울타리_판정',{'울타리 필요 조건 많음(4개 이상)'}):
            add('CK-04','울타리_판정','설치 필요 조건 개수이며 실제 설치 여부는 모름')
        if _is(row,'조도_비교_결과(기준: 표 4.2)',{'P4 평균 5.0 미만','P6(가장 느슨한 등급) 평균 2.0보다 어두움'}):
            add('CK-05','조도_비교_결과(기준: 표 4.2)','해당 측정·등급 비교에 한함')
        if _is(row,'폭2.0m미만(원본)',{'Y'}):
            add('CK-10','폭2.0m미만(원본)','원본 도면 폭이며 현장 보행 유효폭이 아님; 도형값과 불일치 가능')
    elif table == '09_assess_intersection':
        if _is(row,'판정',{'시야 확인 우선'}):
            add('CK-11','판정','건물 기반 시야 확인 후보; 주정차 차량 근거가 없어 CK-07은 생성하지 않음')
    elif table == '10_assess_zone':
        if _is(row,'2022조사_결과',{'울타리 기록 없음(2022)'}):
            add('CK-06','2022조사_결과','2022년 기록 부재이며 현재 시설 부재 확인이 아님')
        if _is(row,'단속카메라300m_결과',{'속도·신호 단속 없음'}):
            add('CK-13','단속카메라300m_결과','300m 내 자료상 집계이며 설치 필요성 확정이 아님')

    candidates=[{'rule_id':ck,'matched_field':field,'observed_value':str(row[field]).strip(),
                 'caution':caution,'judgment_confirmed':False} for ck,field,caution in matches]
    return {'status':'대조 후보 있음' if candidates else '대조 후보 없음',
            'ck_candidates':candidates,
            'detail':'저장된 판정값의 조건 일치 여부만 확인했습니다. 확정 CK 및 승인 문장 연결 입력으로 사용하지 마세요.'}
