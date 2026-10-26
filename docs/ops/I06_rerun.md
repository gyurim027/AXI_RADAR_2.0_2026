# I-06 다시 실행 · 은경, 10/26

기준: 기능정의서 v0.5.3 I-06 "실패하면 원인과 다시 실행 버튼을 보여준다 … 다시 실행은 처음부터 한다. 실패 지점부터 다시 실행하는 것은 확장 단계다." · 화면명세 AD-07 1-2 '로그와 다시 실행'

## API (RADAR 운영자만)
| 주소 | 하는 일 |
|---|---|
| `GET /api/ops/runs` · `GET /api/ops/runs/{id}` | 줄마다 `canRerun` (실패 + 그 기능이 다시 실행 함수를 등록함 → true). 화면은 false면 버튼을 흐리게 |
| `POST /api/ops/runs/{id}/rerun` | 202 `{ok, rerunOf, message}` — 뒤에서 처음부터 다시. 새 실행 기록이 한 줄 생김 → 화면은 실행 기록을 다시 불러 진행 상태를 봄 |

막는 경우: 404 `run_not_found` · 409 `not_failed`(실패한 것만) · 409 `rerun_not_supported`(등록 안 한 기능 — 담당자가 명령으로) · 409 `already_running`(같은 기능·이름·대상이 실행 중, 빠르게 두 번 누름 포함)

새 실행 기록: 첫 단계 로그 `실행 #N(실패)을 처음부터 다시 실행` · `triggered_by` = 누른 운영자 · 원래 실패 기록은 그대로. 다시 실패하면 실패 알림(I-03)도 다시 감.
'어떤 실행을 다시 했는지'는 로그 한 줄로 남긴다 (85에 칸을 더하지 않음).

## 기능 담당자가 할 일 — 다시 실행 함수 등록 (`app/core/rerun.py`)
85 job_run에는 다시 돌릴 입력(파일·옵션)이 남지 않으므로, 연결 표·번호(ref_table·ref_id)로 같은 일을 처음부터 하는 함수를 기능마다 한 번 등록한다.
```python
from app.core.rerun import register_rerun

def _rerun(ref_table, ref_id, user_id):     # 안에서 track(...)을 쓴다 (module 이름은 등록 이름과 같게)
    run_engine(int(ref_id))                  # 예: ref_table='priority_run', ref_id=run_id
register_rerun("ENGINE", _rerun)
```

| 실행 (지금 track을 쓰는 곳) | 기능 · 담당 | 화면 다시 실행 | 필요한 것 |
|---|---|---|---|
| 산정 | 엔진 · 진규 | 아직 안 됨 | 엔진을 `track("산정", …, module="ENGINE", ref_table="priority_run", ref_id=run_id)`로 감싸고 등록 |
| 민원 파일 올리기 · 민원 정제 | C-09·AI-01 · 규림 | 아직 안 됨 | 올린 파일을 서버가 보관하는지(A-04) 확인 뒤 등록 |
| 좌표 · 격자 열 · 법령 개정 · 업무분장 | AI-03 세은 · B-02 · A-11·A-12 은경 | 명령으로 | 입력이 사람 PC의 파일·폴더 (A-11은 Open API를 붙이면 등록 가능) |

## 확인한 것
- [x] `tests/test_core_ops.py` 17개 (다시 실행 4개 추가): canRerun · 처음부터 다시(누른 사람·첫 로그·원래 기록 그대로) · 다시 실패하면 기록·알림 · 막는 경우 5가지
- [x] '같은 것이 실행 중' SQL을 v2.2 시험 DB에서 실행
- [ ] 실제 기능 등록 (첫 대상: 진규님 산정)
