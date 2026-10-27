# AI-03 좌표 반영 (A-07·C-06, 세은)

AI-03 배치(`scripts/ai03_locate.py`)가 만든 `out/ai03/*_update.csv`를 **공용 DB의 좌표 칸**에 쓰는 스크립트다. 기본은 미리 보기이고, `--apply`를 줘야만 쓴다.

## 무엇을 쓰나

| 표 | 키 | 쓰는 칸 |
|---|---|---|
| `parking` — 45 `src_parking_enforce_place` | `row_id` | lat · lon · gid · grid_no · gu_by_coord · admin_dong_by_coord · coord_method · coord_accuracy |
| `signal` — 41 `src_signal_controller` | `row_id` | 위와 같음 |
| `police` — 53 `src_police_signal` | `src_id` | lat · lon · gid · location_method |
| `complaint` — 79 `src_complaint` | `complaint_id` | lat · lon · gid · coord_method · coord_accuracy · (비어 있을 때만) gu · admin_dong_name · 값을 바꾼 시각 `db_last_updated_at` |

파일의 `review_result` 같은 DB에 없는 칸은 읽고 버린다. 점수·순위·다른 표는 건드리지 않는다.

## 안전장치

1. **미리 보기가 기본**: 상태별 건수와 예시를 보여 주고 `out/ai03/apply_plan_<표>_<시각>.csv`에 행별 상태를 적는다. DB는 아무것도 안 바뀌고 `job_run` 기록도 안 남는다.
2. **빈 좌표 행에만**: `WHERE 키 = ? AND lat IS NULL AND lon IS NULL AND gid IS NULL`. 이미 값이 있으면 `이미 좌표 있음`으로 건너뛴다. 같은 파일을 다시 반영해도 안전하다.
3. 미리 보기에서 막는 것: `DB에 없음` · `격자 없음`(gid가 `grid_cell`에 없음) · `칸 길이 초과` · `좌표·gid 불일치`(좌표로 다시 계산한 gid와 다름, pyproj가 있을 때) · `값 이상` · `키 중복`. '반영'이 아닌 상태(이미 좌표 있음 제외)가 있으면 멈추고, 확인한 뒤 `--skip-problems`를 줘야 '반영' 행만 쓴다.
4. **백업**: 반영하기 전에 그 행들의 지금 값을 `out/ai03/backup_<표>_<시각>.csv`에 저장한다. 백업은 이 PC에만 둔다(민원 위치가 들어 있어 드라이브·저장소에 올리지 않는다).
5. **표 하나를 한 거래로**: 한 행이라도 계획과 다르면(그새 누가 바꿈) 그 표 전체를 되돌리고 멈춘다.
6. 반영 뒤 다시 세어 보고(`반영 N행 · 다시 세어 보니 N행`), `85 job_run`에 한 줄 남긴다.
7. **되돌리기**: `--rollback <백업.csv> --apply`. 지금 lat·lon이 우리가 쓴 값과 같은 행만 옛 값으로 되돌리고, 그 뒤에 바뀐 행은 건드리지 않는다.

## 쓰는 법 (저장소 루트, 반영은 행이 적은 표부터)

```
uv run python -m scripts.ai03_apply police    out/ai03/police_update.csv            # 미리 보기
uv run python -m scripts.ai03_apply police    out/ai03/police_update.csv --apply    # 반영
uv run python -m scripts.ai03_apply police    --rollback out/ai03/backup_police_<시각>.csv --apply
```
순서: `police` → `signal` → `complaint` → `parking`. 표 하나를 반영하고 건수를 확인한 뒤 다음으로 간다.
반영 전에 `.env`의 `RADAR_DB_*`가 공용 DB를 가리키는지, HeidiSQL로 확인한 빈 좌표 수와 미리 보기의 '반영' 건수가 맞는지 본다.

## 시험

- `tests/test_ai03_apply.py` 11개 (실제 DB 없이 sqlite): 상태 분류, 길이 초과, gid 불일치, 미리 보기 무변경, 빈 행에만 쓰기·백업, 그새 바뀐 행이 있으면 전체 되돌림, 민원 구·동 빈 칸만 채움, 되돌리기.
- MySQL 8.0.46 시험 DB(v2.3, 실제 데이터)에서 AI-03 파일 4개(경찰 119 · 신호기 218 · 민원 36 · 단속장소 165)를 순서대로 반영 → 빈 좌표 수가 기대대로 줄고(184→65 · 395→177 · 16,530→16,494 · 21,506→21,341), `gid → grid_cell` 외래키가 깨진 행 0 → 같은 파일 재실행은 '이미 좌표 있음'으로 건너뜀 → 전부 되돌리면 네 표의 내용 지문이 처음과 같음.
