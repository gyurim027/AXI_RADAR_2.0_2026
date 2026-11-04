# 격자 EXT_ 열 다시 채우기 — 05 grid_feature · 06 grid_feature_ng (B-02, 세은 재계산용)

작성: 은경 · 2026-10-23 · 기준: SQL v2.1 · 코드: `app/services/grid/ext_columns.py`, 실행: `scripts/grid_rebuild_ext.py`

예전에는 은경 PC의 추출테이블 엑셀(T 시트)로 셌다(`build_ext.py` → `build_final_grid.py`, 이후 `hotspot_fix.py`·`v17_data.py`로 4열 다시 셈).
그 값들은 이미 DB 원천·판정 표에 gid와 같이 들어가 있어서, 이 코드는 **DB 표만 읽어** 같은 규칙으로 센다. 은경 PC 파일이 필요 없다.

## 확인한 것 (SQL v2.1 시험 DB, 10/23)
- 05 EXT_ 21열을 모두 비운 뒤 `--apply` → 표 전체 CHECKSUM이 원래 05와 같음
- 06의 센 값 6열을 비운 뒤 `--apply` → 06 표 전체 CHECKSUM이 원래 06과 같음
- DB 표에서 새로 세는 칸: 05 17열 · 06 6열 = 모든 칸(2,406)이 지금 값과 같음

## 다시 만드는 순서
1. 세은 `build_grid_table.py`로 05 다시 넣기(83열). **`VUL_어린이집수`·`VUL_유치원수`는 26 src_child_facility(공식 목록 512행)로** 센다 — v1.7에서 은경이 공식 목록으로 다시 셌기 때문에 예전 입력(카카오 목록)으로 돌리면 값이 돌아감
2. `uv run python -m scripts.grid_rebuild_ext` (미리 보기) → `--apply`
3. 83 src_road_hazard 파일 다시 실행 → COND_ 포트홀·시선유도봉 4열 (파일 끝 UPDATE가 계산. 84도 FK 때문에 같이)
4. 07~10 판정 다시 계산 (세은)
5. 진규님께 알림 (78 점수 다시 계산)

격자 맞추는 규칙: 위경도(EPSG:4326) → EPSG:5179 → 250m로 나눈 몫이 같은 칸 (적재 규칙 명세서 7장 ①과 같음). 원천 표의 gid가 이 규칙으로 이미 채워져 있다.

## 05 EXT_ 21열
| 칸 | 읽는 표 | 규칙 |
|---|---|---|
| `ext_g_no` | 01 grid_cell.g_no | 은경 격자 번호 그대로 |
| `ext_ped_hotspot_point_cnt` | 39 src_ped_hotspot_5y | 지점 이름(spot_name)+칸 기준 서로 다른 지점 수 |
| `ext_ped_hotspot_repeat_sum` | 39 src_ped_hotspot_5y | 칸에 있는 지점마다 그 지점 첫 행의 repeat_cnt_21_25를 더함 |
| `ext_signal_controller_cnt` | 41 src_signal_controller | gid가 있는 행 수 |
| `ext_hump_crosswalk_cnt` | 42 src_hump_crosswalk | gid가 있는 행 수 |
| `ext_ped_priority_candidate_cnt_2022` | (이어 씀) | 2022 후보지 61곳 — 예전 T11 격자 집계 값. DB gid로 세면 29칸이 다름 |
| `ext_bike_road_endpoint_cnt` | 52 src_bike_road | start_grid_no·end_grid_no를 격자 번호로 바꿔 끝점 수 |
| `ext_parking_enforce_cnt` | 45 src_parking_enforce_place | gid별 enforce_cnt 합 |
| `ext_crosswalk_short_signal_cnt` | 07 assess_crosswalk | sig_check_result가 '부족'으로 시작 |
| `ext_crosswalk_signal_unknown_cnt` | 07 assess_crosswalk | sig_check_result가 '판단 불가' 또는 '현시마다 다름'으로 시작 |
| `ext_crosswalk_lux_under6_cnt` | 07 assess_crosswalk | lux_check_result가 '최소'로 시작 |
| `ext_crosswalk_guide_check_cnt` | 07 assess_crosswalk | guide_check_needed가 있고 '8차로'가 없음 |
| `ext_floor_signal_cnt` | 50 src_floor_signal | gid가 있는 행 수 |
| `ext_floor_signal_missing_crosswalk_cnt` | 50 src_floor_signal | result가 '100m 안 표준'으로 시작 |
| `ext_camera_speed_cnt` | 51 src_enforce_camera_all | enforce_class = 속도 |
| `ext_camera_signal_cnt` | 51 src_enforce_camera_all | enforce_class = 신호 |
| `ext_camera_parking_cnt` | 51 src_enforce_camera_all | enforce_class = 불법주정차 |
| `ext_camera_other_cnt` | 51 src_enforce_camera_all | enforce_class = 기타 |
| `ext_zone_drawing_zone_cnt` | (이어 씀) | 2025 도면 11곳 — 도면 중심점 칸 기준이라 10 assess_zone의 gid(보호구역 칸)로 세면 5칸이 다름 |
| `ext_survey_scope_obstacle` | (이어 씀) | 2022 적치물 조사 범위 — 보행자전용도로 선이 지나는 칸이라 도형이 필요, DB 점만으로는 272칸 중 163~195칸만 나옴 |
| `ext_survey_scope_zone_2022` | (이어 씀) | 2022 보호구역 조사 범위 — DB로 다시 세면 410칸 중 373칸, 나머지는 예전 T11 조사 칸 값 |

**이어 쓰는 4칸** (`data/grid/ext_carry_05_v2_1.csv`, SQL v2.1 값): `ext_ped_priority_candidate_cnt_2022`, `ext_zone_drawing_zone_cnt`, `ext_survey_scope_obstacle`, `ext_survey_scope_zone_2022`. 모두 한 번 조사한 자료(2022 후보지·2025 도면·2022 조사 범위)라 반기 갱신 때 바뀌지 않는다. 원천이 다시 오면 은경에게 요청.

## 06 grid_feature_ng (수치지형도 파생)
| 칸 | 읽는 표 | 규칙 |
|---|---|---|
| `extng_sidewalk_status` | (건드리지 않음) | 보도 도형과 격자의 겹친 면적·폭 — 수치지형도 도형이 있어야 함 |
| `extng_sidewalk_area_m2` | (건드리지 않음) | 보도 도형과 격자의 겹친 면적·폭 — 수치지형도 도형이 있어야 함 |
| `extng_area_weighted_avg_width_m` | (건드리지 않음) | 보도 도형과 격자의 겹친 면적·폭 — 수치지형도 도형이 있어야 함 |
| `extng_width_under2_cnt` | (건드리지 않음) | 보도 도형과 격자의 겹친 면적·폭 — 수치지형도 도형이 있어야 함 |
| `extng_width_under15_cnt` | (건드리지 않음) | 보도 도형과 격자의 겹친 면적·폭 — 수치지형도 도형이 있어야 함 |
| `extng_slope_over_1_12_cnt` | 08 assess_sidewalk | slope_over_1_12 = Y 이고 slope_usable = 참고 가능 |
| `extng_sidewalk_lux_under_p6_cnt` | 08 assess_sidewalk | lux_check_result가 'P6'으로 시작 |
| `extng_fence_cond4_sidewalk_cnt` | 08 assess_sidewalk | fence_result = 울타리 필요 조건 많음(4개 이상) |
| `extng_fence_cond3_no_record_cnt` | 08 assess_sidewalk | fence_cond_cnt ≥ 3 이고 fence_cnt_15m_2022 = 0 |
| `extng_crosswalk_no_refuge_4lane_cnt` | 07 assess_crosswalk | ng_refuge_result에 '없음'·'차로'가 있고 '3'으로 시작하지 않음 |
| `extng_intersection_sight_check_cnt` | 09 assess_intersection | result = 시야 확인 우선 |

- 보도 면적·폭 5칸은 이 스크립트가 바꾸지 않는다. 수치지형도(2025년 판)가 그대로면 안 바뀌고, **격자(01 grid_cell)가 바뀌거나 새 도면이 오면 은경 PC에서** 다시 만든다 (원본·가공 자료는 은경 PC 밖으로 내보내지 않음, 공간정보관리법 제16조·제21조)
- 06 출처 표시: 저작권 국토지리정보원장 · 출처 국토지리정보원 (수치지형도 Ver2.0 1:5,000, 2025년 제작) — RADAR 팀이 집계·판정한 가공값
