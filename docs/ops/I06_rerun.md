# I-06 다시 실행 · 은경, 10/26 (A-11·A-12 등록)

기준: 기능정의서 v0.5.3 I-06 "실패하면 원인과 다시 실행 버튼을 보여준다 … 다시 실행은 처음부터 한다. 실패 지점부터 다시 실행하는 것은 확장 단계다." · 화면명세 AD-07 1-2 '로그와 다시 실행'

## API (RADAR 운영자만)
| 주소 | 하는 일 |
|---|---|
| `GET /api/ops/runs` · `GET /api/ops/runs/{id}` | 줄마다 `canRerun` (실패 + 그 기능이 다시 실행 함수를 등록함 → true). 화면은 false면 버튼을 흐리게 |
| `POST /api/ops/runs/{id}/rerun` | 202 `{ok, rerunOf, message}` — 뒤에서 처음부터 다시. 새 실행 기록이 한 줄 생김 → 화면은 실행 기록을 다시 불러 진행 상태를 봄 |

막는 경우: 404 `run_not_found` · 409 `not_failed`(실패한 것만) · 409 `rerun_not_supported`(등록 안 한 기능 — 담당자가 명령으로) · 409 `rerun_input_missing`(등록한 기능이지만 이 실행에 다시 돌릴 입력이 안 남음 — 예: A-11·A-12 옛 실행) · 409 `already_running`(같은 기능·이름·대상이 실행 중, 빠르게 두 번 누름 포함)

`GET /api/ops/runs/{id}`(한 건)는 로그까지 보고 `canRerun`을 정한다. 목록은 기능 등록만 보고, 누를 때 다시 확인한다.

새 실행 기록: 첫 단계 로그 `실행 #N(실패)을 처음부터 다시 실행` · `triggered_by` = 누른 운영자 · 원래 실패 기록은 그대로. 다시 실패하면 실패 알림(I-03)도 다시 감.
'어떤 실행을 다시 했는지'는 로그 한 줄로 남긴다 (85에 칸을 더하지 않음).

## 기능 담당자가 할 일 — 다시 실행 함수 등록 (`app/core/rerun.py`)
85 job_run에는 다시 돌릴 입력(파일·옵션)이 남지 않으므로, 연결 표·번호(ref_table·ref_id)로 같은 일을 처음부터 하는 함수를 기능마다 한 번 등록한다.
```python
from app.core.rerun import register_rerun

def _rerun(ref_table, ref_id, user_id):     # 안에서 track(...)을 쓴다 (module 이름은 등록 이름과 같게)
    run_engine(int(ref_id))                  # 예: ref_table='priority_run', ref_id=run_id
register_rerun("ENGINE", _rerun)

# (선택) 실행 한 건을 다시 돌릴 수 있는지: 못 하면 이유 글자, 되면 None
register_rerun("A-12", _rerun, check=lambda run: None if 입력이_남음(run) else "입력이 안 남음")
```

**입력이 파일인 기능 (A-11·A-12 방식, `app/services/standards/rerun_hooks.py`)**: 실행을 시작할 때 86 로그에 `다시 실행용 입력: ["--old", "C:\\...", …]` 한 줄(경로는 절대 경로로)을 남기고, 다시 실행할 때 그 줄을 읽어 같은 명령을 같은 입력으로 처음부터 돌린다. 파일은 서버를 켠 PC에 있어야 한다. 원문·민원·개인정보는 넣지 않는다 (파일 경로와 옵션뿐).

| 실행 (지금 track을 쓰는 곳) | 기능 · 담당 | 화면 다시 실행 | 필요한 것 |
|---|---|---|---|
| 산정 | 엔진 · 진규 | 아직 안 됨 | 엔진을 `track("산정", …, module="ENGINE", ref_table="priority_run", ref_id=run_id)`로 감싸고 등록 |
| 민원 파일 올리기 · 민원 정제 | C-09·AI-01 · 규림 | 아직 안 됨 | 올린 파일을 서버가 보관하는지(A-04) 확인 뒤 등록 |
| 법령 개정 확인 · 업무분장 변경 확인 | A-11·A-12 · 은경 | **됨 (10/26)** | 서버 PC에 입력 폴더·파일이 있어야 함. 이 기능 전에 돌린 실행은 입력이 안 남아 409 `rerun_input_missing` → 명령으로 |
| 좌표 · 격자 열 | AI-03 세은 · B-02 | 명령으로 | 입력이 사람 PC의 파일·폴더 — A-11·A-12처럼 입력 한 줄을 남기면 등록 가능 |

## 확인한 것
- [x] `tests/test_core_ops.py` 17개 (다시 실행 4개 추가): canRerun · 처음부터 다시(누른 사람·첫 로그·원래 기록 그대로) · 다시 실패하면 기록·알림 · 막는 경우 5가지
- [x] '같은 것이 실행 중' SQL을 v2.2 시험 DB에서 실행
- [x] 실제 기능 등록: A-11·A-12 (`tests/test_core_ops.py` StandardsRerunTests 5개 — 서버 시작 때 등록 · 경로를 절대 경로로 · 같은 입력으로 처음부터 · 입력 없는 옛 실행 거절 · 실제 A-11 명령이 실패로 남고 입력 줄을 남김)
- [x] 명령이 SystemExit로 멈추거나 Ctrl+C로 끊겨도 '실행 중'으로 남지 않고 '실패'로 (`job_run.track`). 남으면 같은 실행이 계속 '이미 도는 중'으로 막혔음
- [ ] 진규님 산정 등록
