# 격자·검사 (B-01~B-07 · C-07 · F-02 · A-06 · A-08) — 세은

05 `grid_feature`(108열)·06 `grid_feature_ng`(11열)를 다시 만들고, 그 격자로 민원 수·도로 종류를 세며, 원천 표의 이상한 값과 같은 시설을 찾는다. 원천 표는 고치지 않는다 — 결과는 `out/grid/`에 CSV로 내고, DB 반영은 확인 뒤 따로 한다.

## 파일

| 경로 | 기능 |
|---|---|
| `app/services/grid/config.py` · `source.py` | 설정 · 원천 표 읽기 (공용 DB, 또는 `--csv <v2 CSV 폴더>`) |
| `app/services/grid/build_grid_table.py` | B-01·B-03~B-06 원본 공간 자료 → 05 세은 83열 (v1.1.1) |
| `app/services/grid/ext_columns.py` | 05 EXT_ 21열 · 06 센 값 6열 (은경) — `docs/grid/ext_columns.md` |
| `scripts/grid_build_sena.py` | 세은 83열 만들기 → v2 칸 이름 (`data/grid/grid_column_map.csv`) |
| `scripts/grid_build_feature.py` | 05 전체 108열 · 06 11열 합치기 (+ 포트홀·시선유도봉 4열), `--compare`, `--ai03 <폴더>` 전후 비교 |
| `scripts/grid_rebuild_ext.py` | EXT_ 다시 채우기 → `--apply`로 DB 반영 (은경) |
| `scripts/grid_complaint_count.py` | C-07 격자별 민원 수 (`complaint_cnt` · `complaint_cnt_excl_low`) |
| `scripts/grid_road_type.py` | F-02 도로 종류 (링크별 · 격자별, 88 관할표 이름 · 노선) |
| `app/services/quality/issue_format.py` | A-05·A-06·A-08 공통 15칸 문제 목록 (진이님과 맞춤) |
| `scripts/quality_anomaly.py` | A-06 성남 밖·좌표 범위·gid 불일치·구 불일치(행정동 경계)·민원 날짜 |
| `scripts/quality_same_facility.py` | A-08 내용이 같은 행 · 같은 이름·같은 자리 · 같은 자리·다른 이름 |

## 실행 (저장소 루트)

```powershell
# .env: RADAR_DB_* (공용 DB) · RADAR_GRID_RAW_DIR ('최종사용할 데이터' 폴더, B-01~06·F-02·A-06 구 경계에 필요)
uv run python -m scripts.grid_build_sena --compare                  # 세은 83열 (v2와 82/82)
uv run python -m scripts.grid_build_feature --compare               # 05 107/107 · 06 11/11
uv run python -m scripts.grid_build_feature --csv <v2.1 CSV 폴더> --ai03 <AI-03 update 폴더>   # AI-03 반영 전후
uv run python -m scripts.grid_complaint_count
uv run python -m scripts.grid_road_type
uv run python -m scripts.quality_anomaly
uv run python -m scripts.quality_same_facility
```
DB가 열리기 전에는 모든 스크립트에 `--csv <v2.1 통합테이블 CSV 폴더>`를 붙이면 같은 자료로 돈다.

## 확인 (v2.1, 10/23)

05 107/107칸 · 06 11/11칸 v2.1과 같음 · AI-03 반영 시 단속 건수 176,519 → 211,799 (664칸), 신호기 671 → 889 (161칸) · C-07 262,786건 1,264칸 · A-06 1,942건 · A-08 2,911행(묶음 1,202) · F-02 링크 10,669개

## 지킨 것

원천 표 고치지 않음(표시만) · 미조사를 0으로 바꾸지 않음(B-07) · '낮음' 민원도 넣은 값·뺀 값 둘 다(C-07, ISS-033) · 06 보도 면적·폭 5칸은 수치지형도라 은경님이 유지 · 원본 공간 자료는 저장소에 올리지 않음

## 남은 것

DB 반영(05·06·78) 순서: 83열 → `grid_rebuild_ext --apply` → 83 road_hazard → 07~10 판정 → 진규님 알림 · C-07 회차(run_id) 넣는 방식(진규) · F-02 시설-도로 연결(대환) · 문제 목록 표(`data_issue`) 만들기(운영자 화면 때) · 포트홀 탐지 범위(B-07, 83에 운행 범위가 있으면)
