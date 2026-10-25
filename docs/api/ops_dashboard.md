# 운영 대시보드 API (I-05 · 화면명세 AD-01) · 은경, 10/26

`GET /api/ops/dashboard?days=30` · RADAR 운영자만 · 칸 모양은 화면 목업 `frontend/src/mocks/adminServer.js`의 `getDashboard`와 같게 맞춤.

```json
{
 "run": {"id": 3, "name": null, "status": null, "createdAt": "2027.01.05 09:00", "periodStart": "2026.01.01", "periodEnd": "2026.12.31", "adminSampledAt": null},
 "next": {"key": "failed", "text": "실행이 실패했습니다. 원인을 확인하고 다시 실행해 주세요.", "to": "/admin/runs/log", "toLabel": "실행 기록"},
 "data": {"stale": null, "missing": null},
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
| next | 85 job_run 가장 최근 '산정' 실행: 실행 중 → running · 실패 → failed · 회차·산정 기록 없음 → calc | 빠진 자료·검사 오류·검토 중으로 열기는 DB로 알 수 없어 null |
| data | — | stale·missing null — DB에 갱신 주기·예정일 칸이 없음 |
| runs | 85 job_run 최근 days일 | 목업에 없는 running·skipped도 줌 |
| approvals | 62 setting_version 올해: 제안 → pending · 승인 → approved · 돌려보냄 → returned | 목업 이름 '승인 대기'·'돌려받음' = DB '제안'·'돌려보냄' |
| regulations | 89 standard_change에서 운영자가 아직 확인 안 한 수 (seen_at 비어 있음) | 목업의 `!pending`(수정안 승인 대기 제외)은 아직 안 함 |
| notes | 읽지 못한 표·비운 칸의 이유 | 목업에 없음 (화면에 안 써도 됨) |

표 하나를 못 읽어도(옛 SQL·빈 DB) 대시보드 전체는 뜨고, 그 칸만 null + notes에 이유.
