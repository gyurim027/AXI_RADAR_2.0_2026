"""실제 판정 컬럼 명칭/값 기반 대조의 허용/차단 검사 (API,DB,Gemini 미호출)."""
from app.services.ai10_assessment_ck_match import match_assessment_ck as match

def check(name, table, row, expected):
    got=[c['rule_id'] for c in match(table,row)['ck_candidates']]
    assert got == expected,(name,got,expected)
    assert all(c['judgment_confirmed'] is False for c in match(table,row)['ck_candidates'])
    print('PASS | '+name)

cases=[
('점자블록 원본 N','07_assess_crosswalk',{'안내_점자블록_원본':'N'},['CK-03']),
('점자블록 원본 Y','07_assess_crosswalk',{'안내_점자블록_원본':'Y'},[]),
('횡단보도 조도 부족','07_assess_crosswalk',{'조도_비교_결과(기준: 표 5.1 수평면 최소 6 lx)':'최소 수평조도 6 미만 측정점 있음'},['CK-05']),
('신호 판단 불가','07_assess_crosswalk',{'신호_점검_결과':'판단 불가 — 연결된 신호등 없음'},['CK-09']),
('신호 충분','07_assess_crosswalk',{'신호_점검_결과':'충분 — 경찰서 신호값: 모든 보행 현시의 녹색+점멸 ≥ 필요 시간'},[]),
('중간 대피 공간 기록 없음','07_assess_crosswalk',{'NG_중간대피_판정':'4~7차로·중간 대피 공간 없음'},['CK-12']),
('울타리 조건 많음','08_assess_sidewalk',{'울타리_판정':'울타리 필요 조건 많음(4개 이상)'},['CK-04']),
('보도 조도 P4 미만','08_assess_sidewalk',{'조도_비교_결과(기준: 표 4.2)':'P4 평균 5.0 미만'},['CK-05']),
('보도 조도 P6 미만','08_assess_sidewalk',{'조도_비교_결과(기준: 표 4.2)':'P6(가장 느슨한 등급) 평균 2.0보다 어두움'},['CK-05']),
('원본 폭만 대조','08_assess_sidewalk',{'폭2.0m미만(원본)':'Y','폭2.0m미만(도형)':'N'},['CK-10']),
('도형 폭만 Y면 CK10 없음','08_assess_sidewalk',{'폭2.0m미만(원본)':'N','폭2.0m미만(도형)':'Y'},[]),
('교차로 건물 확인 CK11','09_assess_intersection',{'판정':'시야 확인 우선'},['CK-11']),
('주정차 CK07로 오분류 없음','09_assess_intersection',{'판정':'가림 있음'},[]),
('2022 울타리 기록 없음','10_assess_zone',{'2022조사_결과':'울타리 기록 없음(2022)'},['CK-06']),
('2022 조사 대상 아님 제외','10_assess_zone',{'2022조사_결과':'2022 조사 대상 아님(옛 ID 없음) — 모름'},[]),
('300m 단속 카메라 없음','10_assess_zone',{'단속카메라300m_결과':'속도·신호 단속 없음'},['CK-13']),
('단속 카메라 속도 있음','10_assess_zone',{'단속카메라300m_결과':'속도 단속 있음'},[]),
('다중 CK 후보','07_assess_crosswalk',{'안내_점자블록_원본':'N','NG_중간대피_판정':'4~7차로·중간 대피 공간 없음'},['CK-03','CK-12']),
('원문만 있으면 CK 없음','07_assess_crosswalk',{'제목':'점자블록 보수 필요'},[]),
]
for args in cases:check(*args)
assert match('79_src_complaint',{})['ck_candidates']==[]
print('PASS | 79번 원문 CK 추정 차단')
assert match('07_assess_crosswalk',None)['ck_candidates']==[]
print('PASS | 입력 누락 차단')
print('결과: 21/21 통과 | 실제 Gemini/DB 호출 없음')
