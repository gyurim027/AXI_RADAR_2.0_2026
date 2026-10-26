# I-03 실패 알림 메일 · 은경, 10/26

기준: 기능정의서 v0.5.3 I-03 "API 오류, 형식 변경, 계산 실패를 RADAR 운영자에게 알린다. **어드민 알림과 RADAR 운영자가 정한 메일로 보낸다**" · 화면명세 AD-17 '설정 > 알림 설정' · 화면 목업 `adminServer.js` getAlertEmail·saveAlertEmail

## 흐름
1. 어떤 실행이든 `track()` 안에서 실패하면 (85 job_run 실패) → 71 화면 알림 한 줄 (전과 같음)
2. 알림 설정에 메일이 있으면 그 주소로 메일 한 통: 제목 `[RADAR] 실행 실패: <실행 이름>`, 본문은 실행 번호·실패 원인 한 줄(85 cause와 같은 글 — 원문·개인정보·SQL 없음)
3. 메일 결과는 그 실행의 단계 기록(86)에 한 줄: `실패 알림 메일: 2곳에 보냄` / `실패 알림 메일을 보내지 못함 (smtp_failed) — 화면 알림은 남아 있음`
4. 메일은 따로(다른 스레드) 보내서 작업·API 응답을 기다리게 하지 않는다. 메일이 실패해도 작업·화면 알림은 그대로 → AD-17 도움말 "메일이 가지 않으면 다음 접속 때 화면에 띄웁니다"는 71 화면 알림으로 지킴

## API (RADAR 운영자만, `app/api/alert_settings_api.py`)
| 주소 | 하는 일 | 오류 |
|---|---|---|
| `GET /api/admin/alert-email` | `{value, source: "DB"·".env", mailReady}` | — |
| `PUT /api/admin/alert-email` `{value: "a@x.kr, b@y.kr"}` | 저장 → `{ok, value, message: "알림 메일을 저장했습니다."}` · 접근 기록 '설정 변경' | 422 `format` "메일 주소 형식이 맞지 않습니다. 예: name@example.com" · 503 `setting_table_missing` |
| `POST /api/admin/alert-email/test` | 저장된 주소로 시험 메일 | 409 `no_recipient` · 503 `smtp_not_configured` · 502 `smtp_failed`·`smtp_auth_failed` |

목업과 다른 점: 목업은 형식이 틀리면 `{ok:false, code:'format'}`, 서버는 공통 오류 모양 422 `{"error":{code:"format"}}`.

## 받는 메일 저장 곳 — 91 app_setting (SQL 추가 제안)
SQL v2.2에는 운영 설정을 둘 표가 없다. `docs/ops/91_app_setting.sql` (추가만, 두 번 돌려도 그대로)
```sql
CREATE TABLE IF NOT EXISTS app_setting (setting_key PK, setting_value, updated_by → 60 app_user, updated_at)
-- alert_emails = 실패 알림 받을 메일
```
- 표가 생기기 전: 읽기는 `.env`의 `RADAR_ALERT_EMAILS`, 저장(PUT)은 503 `setting_table_missing`
- v2.2 시험 DB에서 만들기·두 번 돌리기·저장·바꾸기 확인 (10/26)

## 보내는 메일 서버 — .env (팀이 정할 것)
```
RADAR_SMTP_HOST= / RADAR_SMTP_PORT=587 / RADAR_SMTP_USER= / RADAR_SMTP_PASSWORD= / RADAR_SMTP_FROM= / RADAR_SMTP_TLS=starttls
```
- 비우면 메일 없이 화면 알림만 (지금 동작과 같음)
- 비밀번호는 각자 `.env`에만. 저장소·채팅·문서에 쓰지 않는다
- 어떤 메일 계정으로 보낼지(팀 공용 계정, 학교·회사 메일 서버 등)는 **팀 결정 필요**

## 확인한 것 / 못 한 것
- [x] `tests/test_alert_mail.py` 8개 (가짜 메일 서버): 실패 → 메일 + 단계 기록 · 메일 서버 없음 → 화면 알림만 · 받는 사람 없음 → 메일 없음 · 형식 검사 · 표 없음 · 운영자만 · 시험 메일
- [x] 91 표 SQL과 저장 코드를 v2.2 시험 DB에서 실제로 실행
- [ ] 실제 메일 서버로 보내기 (팀이 계정을 정한 뒤 `POST /api/admin/alert-email/test`)
