# 민원 적재 (W07-01)

성남데이터넷 '민원 상세정보 현황' **한 달치 파일**을 79 `src_complaint` · 80 `src_complaint_change` · 84 `data_upload`에 넣는다. 담당: 규칙은 `적재 규칙 명세서 v1.1`, 기능은 C-01·C-02·C-09·C-10.
상세 기록·결정·정의서 수정안은 `작업파일/261022/w07-load/`에 있다.

## 쓰는 법
```text
POST /api/c09/uploads?source=…&refDate=2026-09-30&periodStart=2026-09-01&periodEnd=2026-09-30[&dataName=…][&isOfficialRaw=가공본][&fileName=…]
본문: xlsx 파일 그대로 (multipart 아님)
GET  /api/c09/uploads?limit=50      올린 기록 (84 data_upload 최신 순)
```
- 출처·기준일·기간은 필수. 기간은 한 달(1일~말일). 파일 안 민원등록일이 기간 밖이면 거절.
- 한 번에 파일 하나. 파일마다 84에 한 줄. 같은 달을 다시 올리면 바뀐 칸만 고치고 80에 남긴다.
- **RADAR 운영자(`operator`)만** 쓴다 (`Authorization: Bearer <토큰>`). 로그인한 계정이 84 `uploaded_by`에 자동 기록된다.
- 적재는 실행 기록(`track("업로드")`)에 남고, 실패하면 운영자 알림이 쌓인다. 85·86 표가 없는 DB에서는 기록만 못 남기고 적재는 정상이다.
- DB 접속은 `.env`의 `RADAR_DB_*`.

```powershell
# 로컬 DB로 시험 적재 (로컬이 아니면 --allow-shared-db 없이는 멈춘다)
uv run python scripts/load_month.py <xlsx> --month 2026-09 --source "<출처>" --ref-date 2026-09-30
uv run python scripts/load_recurrence.py        # 재발 표시를 DB 값만으로 다시 계산
uv run python scripts/load_verify.py <79_src_complaint.txt> <xlsx> 2026 9   # 79와 민원ID 건수 비교
uv run python -m pytest tests -k load
```

## 흐름
1 올리기(출처·기간) → 형식·기간 확인 → 2 민원ID → 3 칸 쌓기·규칙 가림·본문 좌표→격자 → 4 AI-01(메모리, 새 민원과 결과 없는 민원만) → 원문 버림 → 재발 표시 → 검사 8가지 → 신규/기존/갱신 + 80 → 84 결과.
원문(제목·본문)은 메모리에서만 쓰고 DB·파일·로그에 남기지 않는다. 올린 파일도 저장하지 않는다.

## AI-01 · AI-03
- `app/services/ai01/refine.py`가 있으면 그것을, 없으면 `app/services/load/ai01_stub.py`(가짜)를 부른다. 가짜 결과는 DB에 쓰지 않는다.
- 주소 변환(좌표 채우기)은 AI-03 몫이다. 적재는 본문에 이미 있는 위도·경도만 격자로 바꾼다.

## 공통 파일에 필요한 줄 (PR 설명용)
- `pyproject.toml`: `openpyxl>=3.1`
- `app/main.py` `ROUTER_MODULES`: `("C-09", "app.api.c09_upload_api"),`
- DB(SQL v2.x): 79에 `recurrence_flag`, `recurrence_prev_id` (없으면 재발 표시만 건너뛰고 나머지는 동작)

## 정의서와 다른 점 · 제외한 것
재발 표시는 구현했지만 DB 칸이 있어야 저장된다. 주소 변환(AI-03), 구 불일치 '낮음' 판정, 정보공개청구 회신 파일, CSV 업로드, 행 단위 검사 오류 목록, 백그라운드 실행은 이번 범위에 없다.
