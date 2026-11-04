# A-06·A-08 결과를 data_issue에 넣기 (세은)

`scripts.quality_anomaly`(A-06)·`scripts.quality_same_facility`(A-08)가 만든 공통 15칸 CSV를 `92 data_issue`(SQL v2.3)에 넣는 도구다.
화면 AD-04 오류 목록과 I-05 '검사 오류'가 이 표를 읽는다 (조회 API는 진이님). A-05 줄은 진이님이 넣으므로 이 도구는 **A-06·A-08만** 넣는다.

## 칸 대응

| CSV(공통 15칸) | data_issue | 비고 |
|---|---|---|
| check_fn · error_code | `check_fn` · `error_code` | 지정한 기능과 오류 코드 머리(`A06_`·`A08_`)가 맞아야 함 |
| 검사 | `check_name` | |
| 표 · 행 키 · 칸 | `table_name` · `row_key` · `field_name` | 비면 **빈 글자** (NULL 아님) |
| 값 · 사유 · 묶음 ID | `value_text` · `reason` · `group_id` | |
| 원본 파일 · 원본 행 번호 | `source_file` · `source_row_no` | 비면 빈 글자 · **0** |
| upload_id | `upload_id` | 비면 NULL. 있으면 84 `data_upload`에 있는 번호만 (없으면 `upload_id 없음`으로 막힘) |
| 찾은 시각 | `found_at` | |
| 확인 · 처리 | `review_status` · `resolution` | 새 줄에만 쓰고, **이미 있는 줄에는 절대 덮어쓰지 않음** |
| — | `job_run_id` | 실행 기록 번호가 있으면 넣고 없으면 NULL |

같은 문제의 기준(UNIQUE): `check_fn · error_code · table_name · row_key · field_name · source_file · source_row_no`.

## 안전장치

1. **미리 보기가 기본**: 상태별 건수·오류 코드별 건수·예시를 보여 주고 `out/quality/issue_plan_<기능>_<시각>.csv`에 줄별 상태를 적는다. DB와 `job_run`은 안 바뀐다.
2. 상태: `새로` · `다시 확인(같은 값)` · `값 바뀜` 만 쓴다. `check_fn 다름` · `오류 코드 이상` · `칸 길이 초과` · `키 중복` · `upload_id 없음` · `값 이상`은 막고, 확인한 뒤 `--skip-problems`를 줘야 나머지만 쓴다.
3. 이미 있는 줄은 값·사유·묶음 ID·찾은 시각·실행 번호만 고친다. 운영자 칸은 건드리지 않는다.
4. **기본은 지우지 않는다.** 이번 검사에 안 나온 기존 줄(해결됐을 수 있음)은 건수와 목록(`out/quality/issue_stale_<기능>_<시각>.csv`)만 알려 준다. 지우려면 `--prune-stale`(아래 '정리').
5. 한 거래로 쓴다(넣기·고치기·지우기 모두). 한 줄이라도 막히면 전부 되돌리고 멈춘다.
6. 반영 전에 `out/quality/backup_issue_<기능>_<시각>.csv`(새 줄은 키, 고칠 줄은 옛 값, 지울 줄은 전체 칸)를 만든다. `--rollback`은 새로 넣은 줄을 지우고(운영자가 확인·처리를 적은 줄은 남김) 고친 줄을 옛 값으로 되돌리고, 정리로 지웠던 줄은 **원래 번호(issue_id) 그대로** 되살린다.

## 정리 `--prune-stale` (이번 검사에 안 나온 옛 줄 지우기)

코드를 고쳐 검사 결과가 줄었을 때(예: A-08 ③에서 낮음 좌표를 뺌) 옛 결과의 줄이 `data_issue`에 가짜 경고로 남는다. 그 줄을 지운다. **줄 때만** 지운다.

| 지우는 것 | 안 지우는 것 |
|---|---|
| 이번 파일에 **아예 없고**, 운영자 칸(`review_status`·`resolution`)이 **빈** 같은 검사 기능의 줄 | 운영자 칸이 있는 줄(확인·처리 기록) · 다른 검사 기능(A-05 등)의 줄 · 파일에는 있는데 `--exclude`로 뺀 줄 |

- 미리 보기에 `운영자 칸이 빈 N줄 · 있는 M줄`과 오류 코드·표별 개수, 목록 CSV가 나온다. 목록의 `처리` 칸이 `지움` / `남김(운영자 칸 있음)`.
- **상한**: 한 번에 지울 수 있는 줄은 기존 줄의 10%(최소 50줄). 넘으면 멈춘다(파일이 일부 표만 든 것일 수 있어서). 파일이 맞는 걸 확인했으면 `--prune-max N`.
- 지우기는 넣기·고치기와 **같은 거래**다. 지우는 줄이 그새 운영자가 칸을 적은 줄이면 전부 되돌리고 멈춘다.
- 지운 줄 전체가 백업에 남는다. `--rollback ... --apply`가 그 줄을 같은 번호로 되살린다(번호가 이미 쓰이면 새 번호).
- 끝에 `A-08 전체 N줄(기대 M)`을 다시 세어 보여 준다(기존 + 새로 − 지움).

```
uv run python -m scripts.quality_load_issue A-08 out/grid/a08_groups.csv --skip-problems --prune-stale             # 미리 보기 (무엇이 지워질지)
uv run python -m scripts.quality_load_issue A-08 out/grid/a08_groups.csv --skip-problems --prune-stale --apply     # 반영
```

## 쓰는 법 (저장소 루트)

```
uv run python -m scripts.quality_load_issue A-06 out/grid/a06_flags.csv                 # 미리 보기
uv run python -m scripts.quality_load_issue A-06 out/grid/a06_flags.csv --apply         # 반영
uv run python -m scripts.quality_load_issue A-08 out/grid/a08_groups.csv --apply
uv run python -m scripts.quality_load_issue A-06 --rollback out/quality/backup_issue_A-06_<시각>.csv --apply
```
**빼고 넣기** `--exclude 표:검사이름앞부분` (여러 번 가능). 미리 보기에 `제외(요청)` 건수로 남는다. 예: A-08의 "③ 같은 자리·다른 이름"은 좌표가 5m 안에 모이면 잡는데,
장소 이름 검색으로 찾은 좌표(정확도 '낮음')는 한 건물에 모이는 경우가 많아서 단속장소(`src_parking_enforce_place`)에서는 대부분 진짜 중복이 아니다.
AI-03 좌표 반영 뒤 그 표의 ③이 18,427행으로 전체의 93%를 차지해서 운영자 목록이 쓸모없어지므로 빼고 넣는다.
```
uv run python -m scripts.quality_load_issue A-08 out/grid/a08_groups.csv --exclude "src_parking_enforce_place:③" --skip-problems
```
A-08은 한 행이 여러 쌍에 걸려 같은 줄이 두 번 나올 수 있다. 그 줄은 `키 중복`으로 세고 한 번만 넣는다(`--skip-problems`로 나머지만 씀).
CSV는 **좌표 반영 뒤의 DB를 읽어서** 다시 만든 것을 쓴다(`quality_anomaly`·`quality_same_facility`를 `--csv` 없이 돌리면 DB를 읽는다).

## 시험

- `tests/test_quality_issue_load.py` 15개 (실제 DB 없이 sqlite; 앞 9개 + 정리 6개: 운영자 칸이 있는 줄·A-05 줄 안 지움, 옵션 없으면 안 지움, 상한, exclude한 줄은 안 나온 줄이 아님, 같은 거래, 되살릴 때 원래 번호): 빈 칸→빈 글자·0, A-05 거부·칸 누락, 상태 분류, 빼고 넣기(--exclude), 새 줄 넣기, 다시 돌려도 운영자 칸 유지, 안 나온 줄은 지우지 않음, 한 거래, 되돌리기.
- MySQL 8.0.46 시험 DB(v2.3)에서: 문제 줄이 있으면 `--apply` 거부 → `--skip-problems`로 반영(키 칸이 빈 글자·0으로 들어감) → A-08 반영이 A-06 줄을 안 건드림 → 같은 파일은 '다시 확인' → 값을 바꾸고 운영자 칸을 적은 뒤 다시 반영해도 운영자 칸 유지 → 되돌리기(새 줄 삭제, 확인된 줄 유지).
- 정리는 MySQL 8.0.46(v2.3 표 92·FK 99)에서 실제 A-08 결과 파일 두 벌(옛 3,142줄 / 새 487줄)로 끝까지: 옛 결과 반영 427줄 → 운영자 확인 1줄·A-05 1줄 표시 → 정리 미리 보기(안 나온 25줄 = 지울 24 + 남길 1) → 반영(새로 27 · 지움 24, 전체 430 = 427 + 27 − 24) → 되돌리기(427줄 복귀, 되살린 24줄의 번호 전부 원래와 같음) → 4줄짜리 잘못된 파일은 상한이 막음 → 옵션 없이 반영하면 지움 0.
