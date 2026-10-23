# AI-07 변경 검토표

2026-10-21 제공 develop ZIP 대비: 새 파일 13개, 기존 파일 수정 0개, 삭제 0개.
GitHub 원격에 업로드하거나 develop에 병합하지 않았습니다.

## 추가 경로
- backend/ai07/.gitignore
- backend/ai07/README.md
- backend/ai07/db_server.py
- backend/ai07/local_explainer.py
- backend/ai07/read_only_db.py
- backend/ai07/requirements-db.txt
- backend/ai07/server.py
- backend/ai07/test_db_http.py
- backend/ai07/test_read_only_db.py
- backend/ai07/test_server.py
- docs/api/ai07-db-readonly.md
- docs/ai07/handoff.md
- docs/ai07/change-review.md

## 변경 이유
기존 제출 묶음에서 프론트엔드를 제외하고 AI-07 Python 구현·검사만 별도 폴더로 모았습니다.
Python 구현/검사/의존성 파일 8개는 사용자 제출 ZIP과 바이트 단위로 동일합니다.
설치·실행 안내와 팀 연결 문서는 새 폴더 구조 및 현재 한계에 맞춰 정리했습니다.
API 명세는 경로를 수정하고 이번 제출이 프론트 자동 연결을 포함하지 않는다는 점을 명시했습니다.

## 검사
python -m unittest discover -s backend/ai07 -v: 기존 검사 16개 통과.
실제 DB 접속 및 외부 LLM 호출 없음. 프론트엔드 수정 없음.
팀 규칙의 npm lint/build는 기존 프론트엔드 검사를 뜻하며 이번 Python 전용 묶음에서는 실행하지 않았습니다.
PR 작성 때 변경 범위와 Python 검사 결과를 적고 팀의 필수 검사는 따릅니다.

## 네가 확인할 내용
- 이번에는 backend/ai07 및 docs의 AI-07 파일만 추가합니다.
- 점수/순위를 계산하지 않으며 DB를 변경하지 않습니다.
- GitHub 브랜치 업로드와 develop 병합은 다른 단계입니다.
- 공유 서버 운영 통합과 전체 근거 연결은 후속 작업입니다.
