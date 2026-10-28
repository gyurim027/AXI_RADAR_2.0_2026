# AI-03 좌표 결과 조회 API (세은)

화면: **AD-04 낮음 민원 · 지도**, **AD-04 위치 미확인 탭**(아래 `/unlocated`) · 데이터: 79 `src_complaint` (좌표) ← 05 `grid_feature` (구) · SQL v2.1 · 읽기만 한다.

AI-03이 찾은 좌표 중 정확도가 **'낮음'**인 민원을 화면에 주는 API다. '낮음'은 정확한 주소 좌표가 아니라 **대략 위치**다
(장소 이름 검색·내부 자료 대조로 찾은 근처 건물 좌표, 민원 본문의 위치값 등). 화면에서 '대략 위치'로 보여 주고, 사람이 확인할 수 있게 한다.
공용 DB 기준(AI-03 좌표 반영 뒤, 10/27) **390건**: 분당구 203 · 수정구 127 · 중원구 60, 구가 빈 격자의 민원은 0건. (반영 전 v2.1은 354건)

## 주소

`GET /api/ai03/low-complaints?gu=&limit=&offset=`

| 칸 | 뜻 | 기본 |
|---|---|---|
| `gu` | 구(수정구·중원구·분당구). 없으면 볼 수 있는 구 전체 | 없음 |
| `limit` | 한 번에 줄 건수 (1~1000) | 200 |
| `offset` | 건너뛸 건수 | 0 |

정렬: 접수일 최근 순, 같으면 민원 ID 순.

## 권한과 접근 기록

- 로그인 필수 (`Authorization: Bearer <토큰>`). 토큰이 없으면 401 `login_required`.
- 구 도로관리팀(`district`)은 **자기 구만** 본다. 다른 구를 지정하면 403 `forbidden_gu`. 구가 비어 있는 격자의 민원은 못 본다.
- 시 도로과(`city`)·RADAR 운영자(`operator`)는 3개 구 전체와 구가 비어 있는 격자(44개)의 민원까지 본다.
- **민원 점 위치라서 볼 때마다 접근 기록**(70 `access_audit`, 종류 `민원 점 위치`, 업무 목적 `좌표 정확도 낮음 민원 확인`)을 남긴다.
  로그인 한 번 동안 구·업무 목적이 같으면 한 줄만 남는다. 구 지정 없이 전체를 보면 3개 구에 한 줄씩 남는다. 기록은 수정·삭제하지 않는다.

## 응답 예시 (값은 시험용 가짜)

화면에는 camelCase로 간다(공통 응답 규칙).

```json
{
  "total": 390,
  "limit": 200,
  "offset": 0,
  "complaints": [
    {
      "complaintId": "C-EXAMPLE-0001",
      "sourceType": "일반 민원",
      "receivedDate": "2025-06-12",
      "locationText": "예시 위치 글자",
      "gu": "분당구",
      "adminDongName": "예시동",
      "gid": "다사00aa00aa",
      "lat": 37.40,
      "lon": 127.10,
      "coordMethod": "주소 변환(장소 이름 검색)",
      "coordAccuracy": "낮음",
      "methodKind": "장소"
    }
  ]
}
```

| 칸 | 뜻 |
|---|---|
| `total` | 조건에 맞는 전체 건수 (페이지 나누기용) |
| `complaintId` | 79 민원 ID |
| `gu` | 좌표가 들어 있는 격자의 구. 구가 빈 격자면 `null` |
| `gid` | 250m 격자 번호 |
| `lat`·`lon` | 대략 위치 좌표 (WGS84) |
| `coordMethod` | 좌표를 찾은 방법의 원문 (예: `주소 변환(장소 이름 검색)`, `원본 좌표(본문 위치값)`) |
| `methodKind` | 화면 표시용 한 단어: `장소` · `주소` · `본문 위치값` · `내부 대조` · `기타` |
| `coordAccuracy` | 항상 `낮음` |

## 오류

공통 모양 `{"error": {"status", "code", "message"}}`.

| 상태 | code | 언제 |
|---|---|---|
| 401 | `login_required` · `token_expired` · `invalid_token` | 로그인이 없거나 시간이 지남 |
| 403 | `forbidden_gu` | 구 도로관리팀이 다른 구를 지정함 |
| 422 | `invalid_input` | `limit`·`offset` 범위를 벗어남 (공통 처리기가 내는 값) |
| 503 | `db_read_failed` | DB를 읽지 못함, 또는 접근 기록을 못 써서 목록을 안 보여 줌 (12_오류 케이스 ERR-11). 연결 주소·오류 원문은 응답에 안 담는다 |
| 503 | `db_not_configured` | 서버에 DB 접속 정보가 없음 (ERR-13, 사용자에게는 ERR-11 문구로 보임) |

## 참고

- 좌표 반영(빈 좌표 행에만 쓰기)은 이 API가 아니라 AI-03 반영 단계가 한다. 이 API는 읽기만 한다.
- 민원 본문·요약문(`masked_summary`)은 내려주지 않는다. `locationText`는 79의 `location_text`(신고에 적힌 위치 글자)를 그대로 주므로, 위의 로그인·구 제한·접근 기록 대상이다.
- 시험: `tests/test_ai03_location_api.py` 17개 · `tests/test_ai03_unlocated.py` 13개 (가짜 저장소·가짜 접근 기록, 실제 DB 없이 돈다). 그 밖에 MySQL 8.0.46 + 실제 접근 기록 저장소로 서버 켜짐(200, 접근 기록 구마다 한 줄)·꺼짐(503)을 확인했다.

---

## 위치 미확인 현황 (AD-04 위치 미확인 탭)

화면: **AD-04 위치 미확인 탭** · 데이터: 원천 표(41 `src_signal_controller` · 45 `src_parking_enforce_place` · 53 `src_police_signal` · 79 `src_complaint`)의 좌표 칸 · 읽기만 한다.

검사 결과(`data_issue`, 진이님의 `GET /api/data-issues`)와 따로 간다. 좌표가 빈 행은 줄 수가 너무 많아(단속장소만 1만 곳이 넘는다) 목록 대신
**표별 좌표 확보 현황**과 **단속 건수 상위 N곳**을 준다 (규림님 10/28 정리).

`GET /api/ai03/unlocated?limit=`

| 칸 | 뜻 | 기본 |
|---|---|---|
| `limit` | 상위 목록 건수 (1~100) | 20 |

- **좌표 없음** = `lat` 또는 `lon`이 비어 있음.
- 로그인 필수, **RADAR 운영자(`operator`)만** 본다. 구 도로관리팀(`district`)·시 도로과(`city`)는 403 `forbidden_role`.
- 건수와 단속장소 이름·단속 건수만 준다. **시설·민원의 좌표 값은 내려주지 않으므로 접근 기록은 남기지 않는다.**

### 응답 예시 (값은 예시)

```json
{
  "coverage": [
    {"table": "src_parking_enforce_place", "label": "단속장소", "totalRows": 23503, "missingRows": 14483, "missingRate": 61.6},
    {"table": "src_signal_controller", "label": "신호기", "totalRows": 1066, "missingRows": 177, "missingRate": 16.6},
    {"table": "src_police_signal", "label": "경찰 신호", "totalRows": 384, "missingRows": 65, "missingRate": 16.9},
    {"table": "src_complaint", "label": "민원", "totalRows": 281153, "missingRows": 16494, "missingRate": 5.9}
  ],
  "top": {
    "table": "src_parking_enforce_place",
    "limit": 20,
    "totalMissing": 14483,
    "items": [
      {"rowKey": "row_id=1234", "name": "OO사거리 앞", "enforceCnt": 1520}
    ]
  }
}
```

| 칸 | 뜻 |
|---|---|
| `coverage[].table` · `label` | 원천 표 이름 · 화면에 보일 이름 (단속장소 · 신호기 · 경찰 신호 · 민원) |
| `coverage[].totalRows` · `missingRows` | 전체 행 수 · 좌표 없는 행 수 |
| `coverage[].missingRate` | 좌표 없는 비율 (%, 소수 첫째 자리). 전체가 0이면 0.0 |
| `top.table` | 상위 목록의 표 (단속 건수 칸이 있는 단속장소만) |
| `top.totalMissing` | 좌표 없는 단속장소 전체 곳수 (`전체 n곳 중 N곳` 표시용) |
| `top.items[]` | 좌표가 빈 단속장소를 단속 건수가 많은 순서로. 같으면 `row_id` 순 |
| `top.items[].rowKey` | `row_id=번호` (data_issue의 행 번호 모양과 같다) |
| `top.items[].enforceCnt` | 이 장소의 단속 건수 (없으면 `null`) |

AI-03 좌표 반영 뒤 좌표가 채워지면 `missingRows`가 줄어든다. 값은 호출할 때마다 DB에서 센다(4개 표 합쳐 0.2초 안팎, MySQL 8.0.46·민원 28만 행 기준).

### 오류

| 상태 | code | 언제 |
|---|---|---|
| 401 | `login_required` · `token_expired` · `invalid_token` | 로그인이 없거나 시간이 지남 |
| 403 | `forbidden_role` | 운영자가 아님 |
| 422 | `invalid_input` | `limit` 범위를 벗어남 |
| 503 | `db_read_failed` · `db_not_configured` | DB를 읽지 못함 · DB 접속 정보 없음 (12_오류 케이스 ERR-11 · ERR-13, 연결 주소·오류 원문은 안 내보낸다) |
