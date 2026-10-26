# 운영 대시보드 API (I-05 · 화면명세 AD-01) · 은경, 10/26

`GET /api/ops/dashboard?days=30` · RADAR 운영자만 · 칸 모양은 화면 목업 `frontend/src/mocks/adminServer.js`의 `getDashboard`와 같게 맞춤.

```json
{
 "run": {"id": 3, "name": null, "status": null, "createdAt": "2027.01.05 09:00", "periodStart": "2026.01.01", "periodEnd": "2026.12.31", "adminSampledAt": null},
 "next": {"key": "failed", "text": "실행이 실패했습니다. 원인을 확인하고 다시 실행해 주세요.", "to": "/admin/runs/log", "toLabel": "실행 기록"},
 "data": {"stale": 2, "missing": 2, "unscheduled": 51, "total": 54},
 "runs": {"days": 30, "success": 1, "failure": 1, "warning": 0, "running": 0, "skipped": 0},
 "approvals": {"pending": 2, "approved": 5, "returned": 1},
 "regulations": 4,
 "alerts": {"unread": 1}, "uploads": {"days": 30, "count": 7, "lastAt": null}, "access": {"today": 3},
 "notes": ["회차 상태(산정 중·검토 중·확정)는 DB에 칸이 없어 비움 (D-10)", "자료 최신 여부(갱신 예정일 지남·빠짐)는 DB에 갱신 주기·예정일 칸이 없어 비움 (A-01)"]
}
```

| 칸 | 읽는 곳 | 목업과 다른 점 |
|---|---|---|
| run | 77 priority_run 가장 최근 회차 (v2.2 칸: 민원 기간·표본 완료) | `name`·`status`는 null — 77에 회차 이름·상태 칸이 없음 (D-10은 아직 개발용 메모리 저장) |
| next | ① 빠진 자료가 있으면 missing("빠진 자료 N종을 올려 주세요.") ② 85 가장 최근 '산정' 실행: 실행 중 → running · 실패 → failed · 회차·산정 기록 없음 → calc | 검사 오류(92 data_issue)·검토 중으로 열기(77 회차 상태)는 아직 연결 전 |
| data | 56 source_list + 84 data_upload (SQL v2.3) — 아래 '자료 최신 여부 규칙' | 목업에 없는 unscheduled(일정 미설정)·total(56 전체 자료 수)도 줌. v2.2 DB면 모두 null + notes |
| runs | 85 job_run 최근 days일 | 목업에 없는 running·skipped도 줌 |
| approvals | 62 setting_version 올해: 제안 → pending · 승인 → approved · 돌려보냄 → returned | 목업 이름 '승인 대기'·'돌려받음' = DB '제안'·'돌려보냄' |
| regulations | 89 standard_change에서 운영자가 아직 확인 안 한 수 (seen_at 비어 있음) | 목업의 `!pending`(수정안 승인 대기 제외)은 아직 안 함 |
| notes | 읽지 못한 표·비운 칸의 이유 | 목업에 없음 (화면에 안 써도 됨) |

## 자료 최신 여부 규칙 (10/26 진이·규림 합의 + 은경)
- 대상 주기: 월간 · 분기 · 반기 · 연간 (56 refresh_cycle)
- stale(갱신 예정일 지남): 주기가 있고 next_refresh_date가 오늘보다 앞. 정상 확보 때 예정일이 자동으로 앞으로 가므로(A-02·A-03) 지나 있으면 아직 새로 확보 안 한 것
- missing(빠짐): 주기가 있는데 84에 source_id가 같고 check_result가 VALIDATION_PASSED · VALIDATION_WARNING인 줄이 하나도 없음
  (CSV_STRUCTURE_PASS_ONLY · VALIDATION_FAILED · 빈 값은 확보로 안 셈 → 기존 초기 적재 7줄은 확보로 안 셈)
- unscheduled(일정 미설정): 주기가 비었거나 '수시' — 지연·빠짐으로 세지 않음. v2.3을 막 넣은 DB는 54개 모두 여기
- 확인: v2.3 시험 DB에서 자료 3개에 주기를 넣고 1개만 VALIDATION_PASSED로 이었을 때 stale 2 · missing 2 · unscheduled 51

표 하나를 못 읽어도(옛 SQL·빈 DB) 대시보드 전체는 뜨고, 그 칸만 null + notes에 이유.
