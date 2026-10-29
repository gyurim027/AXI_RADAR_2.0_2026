# 운영 대시보드 API (I-05 · 화면명세 AD-01) · 은경, 10/26 (기능정의서 v0.5.4 반영)

`GET /api/ops/dashboard?days=30` · RADAR 운영자만 · 칸 모양은 화면 목업 `frontend/src/mocks/adminServer.js`의 `getDashboard`와 같게 맞춤.

```json
{
 "run": {"id": 3, "name": null, "status": null, "createdAt": "2027.01.05 09:00", "periodStart": "2026.01.01", "periodEnd": "2026.12.31", "adminSampledAt": null},
 "next": {"key": "failed", "text": "실행이 실패했습니다. 원인을 확인하고 다시 실행해 주세요.", "to": "/admin/runs/log", "toLabel": "실행 기록"},
 "data": {"stale": 2, "missing": 2, "unscheduled": 51, "total": 54},
 "checks": {"fix": 1301, "reference": 3147, "unreviewed": 4448},
 "criteria": {"id": 12, "kind": "가중치", "label": "가중치 v3", "pending": true, "status": "승인 대기", "at": "2026.10.20", "to": "/admin/standards/criteria/12", "toLabel": "산정 기준 상세"},
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
| next | v0.5.4 AD-01 1-1 순서. ① 빠진 자료 → missing("빠진 자료 N종을 올려 주세요.") ② 미확인 검사 오류 중 고칠 수 있는 것(A-05) → checks("검사에서 걸린 자료 N건을 고쳐 주세요.", 검사 결과 화면) ③ 85 가장 최근 '산정' 실행: 실행 중 → running · 실패 → failed · 회차·산정 기록 없음 → calc | 검토 중으로 열기 · 3개 구 확정 기다림은 77 회차 상태 칸이 생기면 (D-10, 대환) |
| checks | 92 data_issue에서 review_status가 NULL(= 미확인, 칸 설명)인 수 (SQL v2.3). `fix` = check_fn A-05(형식·빈칸·중복, 고쳐서 다시 올림) · `reference` = 그 밖(A-06 이상한 값·A-08 같은 시설 의심 — 기능정의서 1-2 "고치지 않고 표시만") · `unreviewed` = 합. 다음 할 일은 `fix`만 봄 (10/27 세은 제안). 10/29 규림·세은·진이 정리(진이 `/api/data-issues`와 같은 기준): A-05 중 `A05_DUPLICATE_ROW`(중복 의심)는 `reference`로, `A05_COORD_RANGE`(좌표 범위)는 A-06에 같은 오류가 있어 세지 않음 → 공용 DB fix 0 · reference 4,425 | 목업은 형식·값 검사 결과 수. 화면에서 `reference`는 '확인 필요(참고)'로 따로 보임. 92가 없는 DB면 null + notes |
| data | 56 source_list + 84 data_upload (SQL v2.3) — 아래 '자료 최신 여부 규칙' | 목업에 없는 unscheduled(일정 미설정)·total(56 전체 자료 수)도 줌. v2.2 DB면 모두 null + notes |
| runs | 85 job_run 최근 days일 | 목업에 없는 running·skipped도 줌 |
| approvals | 62 setting_version 올해: 제안 → pending · 승인 → approved · 돌려보냄 → returned | 목업 이름 '승인 대기'·'돌려받음' = DB '제안'·'돌려보냄' |
| criteria | 62 setting_version 중 산정 설정(가중치·기준값·우선 확인 조건, I-02와 같은 범위): 승인 대기(제안) 중 가장 최근 → 없으면 승인된 것 중 가장 최근. 없으면 null | v0.5.4 AD-01 6-1 새 카드. `to`는 지금 화면 주소(`/admin/standards/criteria/{id}`) — v0.5.4에서 산정 기준이 '산정' 메뉴 아래로 옮겨지면 화면 주소에 맞춰 바꿈 |
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

## 종 아이콘 알림 (I-03, AD-00 3-1) — 10/28
`GET /api/ops/notifications?unread=true` · `POST /api/ops/notifications/{id}/read` (네 종류 모두 같은 주소)

| kind | 언제 생기나 | 원인 표 | 언제 닫히나 |
|---|---|---|---|
| failure | 실행이 실패할 때 (job_run) | 85 | 운영자가 확인 |
| staleData | 주기가 정해진 자료의 다음 갱신 예정일이 오늘보다 앞 | 56 | 확인 · 또는 새 자료를 올려 예정일이 바뀌면 '해결됨' |
| regulation | 운영자가 아직 확인하지 않은 규정 변경 | 89 | 확인 · 또는 '규정 변경' 화면에서 확인하면 '해결됨' |
| approval | 최근 30일에 승인·반려된 제안 (문구는 '반려') | 62 | 확인 |

- 실패 말고 세 종류는 목록(또는 대시보드)을 열 때 원인 표를 보고 71 `alert_delivery`에 한 번만 남긴다 (`alert_kind`·`ref_table`·`ref_id`, UNIQUE). 읽음은 71 `acknowledged_at`.
- 응답 한 줄: `id` · `kind` · `runId`(실패) · `refTable`·`refId`(나머지) · `date` · `text` · `read` · `status`(보냄 · 확인함 · 해결됨)
- 필요한 SQL: `docs/ops/sql_71_alert_kind.sql` (다음 통합 SQL v2.4에 넣음). 이 SQL 전 DB에서는 실패 알림만 보이고 대시보드 notes에 이유가 남는다.

