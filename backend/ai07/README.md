# AI-07 Python backend

현재 단계: PC 내부 개발·연결 시험용. 팀 공통 서버에 연결하거나 운영 배포한 상태는 아닙니다.
계산된 점수·순위를 설명하며 점수·순위를 새로 계산하지 않습니다. 외부 LLM SDK/API 키가 필요하지 않습니다.

## 파일
- db_server.py: DB 조회용 GET API, 로컬 8007 포트
- read_only_db.py: 고정 SELECT, 읽기 전용 거래, 저장값 설명문
- server.py: 공통 HTTP 처리 및 별도 가상 입력 POST 시험 서버. db_server.py에서도 가져오므로 삭제하지 않습니다.
- local_explainer.py: 기존 가상 입력/후보 입력 문장 틀 함수
- test_db_http.py, test_read_only_db.py, test_server.py: 실제 DB 없이 실행하는 검사
- requirements-db.txt: 실제 DB 연결에 필요한 도구

## PowerShell 실행: 저장소 최상위에서
```powershell
# AI-07 폴더로 이동
Set-Location .\backend\ai07
# Python 실행 환경 생성
python -m venv .venv
# DB 연결 도구 설치
.\.venv\Scripts\python.exe -m pip install -r requirements-db.txt
# 실제 DB에 접속하지 않는 검사
.\.venv\Scripts\python.exe -m unittest discover -s . -v
# DB 읽기 서버 시작; 접속 정보는 화면에서 입력
.\.venv\Scripts\python.exe db_server.py
```
접속 정보는 담당자에게 확인하고 코드·문서·GitHub에 적지 않습니다. 데이터베이스 이름은 현재 코드에 mysqlteam02db로 고정되어 있습니다. 다른 환경이면 팀과 확인 후 수정합니다.
서버는 127.0.0.1:8007에서만 열립니다. 종료는 Ctrl+C입니다.
별도 PowerShell에서 실행 목록을 확인할 수 있습니다.
```powershell
Invoke-RestMethod 'http://127.0.0.1:8007/api/ai07/db/runs'
```
DB가 비어 있으면 no_results가 정상입니다. 결과를 만들려고 DB에 INSERT하거나 SQL을 재실행하지 않습니다.

## 연결 방법
API 명세: [ai07-db-readonly.md](../../docs/api/ai07-db-readonly.md)를 참조합니다.
팀 연결 안내: 저장소 최상위 docs/ai07/handoff.md.
Python 파일을 모듈로 가져오는 기존 팀 서버가 있으면 import 경로와 라우터를 맞추는 작업이 필요합니다. 현재 파일은 이 폴더에서 스크립트로 실행하는 구조입니다.

## 별도 가상 입력 시험
python server.py는 POST /api/ai07/explain을 제공하는 다른 시험 모드입니다.
DB 모드(db_server.py)는 POST를 거부합니다. 두 서버를 같은 포트로 동시에 실행하지 않습니다.
기존 프론트엔드를 자동 연결하거나 수정하지 않으며, 이 묶음에는 프론트엔드 파일이 없습니다.
