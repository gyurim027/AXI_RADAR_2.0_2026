# 계정 관리(I-01)·접속 기록(I-04) API — 은경, 10/26

- 코드: `app/api/accounts_api.py`, `app/services/accounts/repository.py` · 표: 60 `app_user`, 61 `role_change_log`, 70 `access_audit` (SQL v2.1~v2.2)
- 연결 화면: 어드민 **계정** 화면, 어드민 **접속 기록** 화면. 모양은 프론트 목업 `frontend/src/mocks/adminServer.js`의 `listAccounts` · `createAccount` · `setAccountStatus` · `listAccess`와 같다.
- 모두 **RADAR 운영자만** (`Authorization: Bearer <token>`). 다른 역할은 403 `forbidden_role`, 로그인 안 하면 401 `login_required`.
- 응답 칸 이름은 camelCase (공통 규칙). 오류는 `{"error": {"status", "code", "message"}}` 한 모양.

## 1. 계정 목록 — `GET /api/admin/accounts` (목업 `listAccounts`)
```json
{
  "rows": [
    {"id": "suj", "name": "김수정", "role": "구 도로관리팀", "gu": "수정구", "team": "건설과 도로관리팀", "status": "사용 중", "last": "2026.10.25"},
    {"id": "city", "name": "박사례", "role": "시 도로과", "gu": "-", "team": "도로과 도로관리팀", "status": "사용 중", "last": "-"}
  ],
  "log": [
    {"id": "rl-3", "at": "2026-10-26", "name": "김수정", "from": "구 도로관리팀 (수정구)", "to": "구 도로관리팀 (중원구)", "by": "운영자", "reason": "인사 이동"}
  ],
  "roles": ["시 도로과", "구 도로관리팀", "RADAR 운영자"]
}
```
- `last` = 마지막 로그인 날짜 (70 접속 기록의 '로그인'에서 읽음). 로그인한 적 없으면 `-`
- `log` = 61 권한 변경 기록 (최근 순). 주기는 `from: "-"`, 거두기(멈춤)는 `to: "-"`. 목업에 없던 `reason` 칸이 더 있다.

## 2. 계정 만들기 — `POST /api/admin/accounts` (목업 `createAccount`)
요청 `{"role": "구 도로관리팀", "gu": "분당구", "team": "보도관리팀", "name": "최보도", "loginId": "bundang-sidewalk2"}` (`team`은 비우면 기본값)
```json
{"ok": true, "id": "bundang-sidewalk2", "tempPassword": "q3Zr0x_8LmPa", "notice": "임시 비밀번호는 지금 한 번만 보입니다. 받는 분께 직접 전해 주세요."}
```
- **목업과 다른 점**: 임시 비밀번호를 한 번만 돌려준다(DB에는 해시만). 화면에서 한 번 보여 주고 다시 불러올 수 없음을 안내해 주세요.
- 실패는 목업의 `{ok: false, code}` 대신 오류 모양으로 온다:

| 목업 code | 서버 | 뜻 |
|---|---|---|
| `guRequired` | 400 `gu_required` | 구 도로관리팀인데 구를 안 고름 |
| `required` | 400 `required` | 이름·아이디 빈칸 |
| `duplicate` | 409 `duplicate` | 이미 있는 아이디 |
| - | 400 `invalid_role` | 역할이 3개 중 하나가 아님 |

## 3. 사용 멈추기·다시 쓰기 — `PATCH /api/admin/accounts/{loginId}/status` (목업 `setAccountStatus`)
요청 `{"status": "멈춤"}` 또는 `{"status": "사용 중"}` (`reason` 선택) → `{"ok": true, "changed": true}` (이미 그 상태면 `changed: false`)
- 내 계정은 403 `self_change`, 없는 계정은 404 `account_not_found`
- 멈추면 그 계정의 **로그인은 403 `inactive_account`**, 이미 받은 토큰도 다음 요청부터 **401 `account_inactive`**

## 4. 역할·담당 구 바꾸기 — `PATCH /api/admin/accounts/{loginId}/role` (목업에 없음, 기능정의서 I-01 "권한을 바꾼 기록")
요청 `{"role": "구 도로관리팀", "gu": "중원구", "reason": "인사 이동"}` (`reason` 필수) → `{"ok": true, "changed": true}`
- 바뀐 사람의 옛 토큰은 다음 요청부터 401 `role_changed` → 다시 로그인

## 5. 임시 비밀번호 다시 만들기 — `POST /api/admin/accounts/{loginId}/password-reset` (목업에 없음)
→ `{"ok": true, "id": "suj", "tempPassword": "...", "notice": "..."}` · 로그인 잠금(5번 틀림)도 같이 풀린다

## 6. 접속 기록 — `GET /api/admin/access?days=30&accountId=suj&action=로그인` (목업 `listAccess`)
```json
{
  "actions": ["로그인", "민원 점 위치", "파일 내려받기", "결정", "승인", "설정 변경"],
  "accounts": [{"value": "suj", "label": "김수정 (수정구청 건설과 도로관리팀)"}],
  "rows": [
    {"id": 41, "at": "2026-10-25T09:11:00", "atLabel": "2026.10.25 09:11", "actor": "수정구청 건설과 도로관리팀", "accountId": "suj",
     "who": "김수정 (수정구청 건설과 도로관리팀)", "ip": "10.12.8.21", "action": "로그인", "target": "-", "reason": "로그인"}
  ]
}
```
- `accountId`, `action`은 비우거나 `전체`면 모두. 최근 순, 최대 500줄(`limit`로 조정)
- **읽기만 한다.** 고치거나 지우는 주소는 없다 (고시 제8조).
- **목업과 다른 점**: `actions`는 서버가 실제로 남기는 6가지다. 목업의 `화면 열람`, `사용자 화면 보기`는 아직 서버가 남기지 않는다(필요하면 은경에게 요청).

## 7. 계정 바꾸는 일의 기록
계정 만들기·멈춤·다시 쓰기·역할 바꾸기·비밀번호 다시 만들기는 모두 70에 `설정 변경`으로 한 줄씩 남는다 (`target` 예: `계정 만들기 suj`). 비밀번호 원문은 어디에도 남지 않는다.
