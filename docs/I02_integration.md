# I-02 실제 설정 조회와 I-07 처리 결과 연결

## 구현 범위

업무 원본 v5.8(8)의 I-02 중 운영자의 저장된 산정 설정 조회와 I-07 처리 결과 확인을 연결했다. 기준은 제공된 W05 3bd89291e9e5926f0b26153bdcfaabf3cd7a7bda, AI05 3cc5cd50a27a8c0656f4e91da41f2a23070bfeaa와 기존 I-07 변경본이다. 최신 팀 소스에 같은 기능이 있는지는 미확인이다. GitHub 재연결은 반복하지 않았다.

- 62의 가중치·기준값·우선 확인 조건만 조회한다. 담당 부서 표 생성·반영은 기존 F-05·I-07 경로를 유지한다.
- 조회는 RADAR 운영자 JWT만 허용한다. 승인·돌려보냄은 기존 시 도로과 JWT만 허용한다. 양쪽은 같은 setting_version_id를 사용한다.
- version_label이 같아도 ID로 목록·상세를 구분한다. 최신 승인 설정이나 활성 설정을 자동 선택하지 않는다.
- content_ref는 원문 그대로 표시한다. JSON·숫자·URL로 해석하거나 파일을 열지 않으며, HTML 문자열도 실행하지 않는다. NULL은 미기록으로 표시한다.
- 설정 생성·숫자 편집·승인 요청 작성·계산 미리보기·엔진 선택·62/77 사용 버전 연결은 이번 완료 범위가 아니다. 원본 설정 화면의 목업 수치나 성공 응답으로 대신하지 않는다.
- 민원·결측·점수·상세근거 API는 병렬 1 담당 범위를 유지한다. H-02·77·78 및 82·07~10 공동 책임은 별도 계약 확인 대상으로 유지한다.

## API

| 경로 | 역할 | 동작 |
|---|---|---|
| GET /api/settings/versions | operator | kind, status, limit(1~500), offset 필터. versions·hasMore·limit·offset 반환 |
| GET /api/settings/versions/{id} | operator | 62의 실제 단건 원문과 처리 기록 |
| POST /api/approvals/{id}/review | city | 기존 I-07 승인·돌려보냄. 산정 설정은 부서표 적용·계산 없이 승인 기록만 변경 |

kind는 가중치·기준값·우선 확인 조건, status는 제안·승인·돌려보냄을 사용한다. 없는 ID 또는 다른 설정 종류의 ID는 404, 잘못된 필터는 422, 무인증은 401, 역할 위반은 403이다. 조회 실패는 500 오류로 남기며 빈 목록이나 목업 성공으로 바꾸지 않는다. 설정 생성·수정 API는 추가하지 않았다.

## 기존 화면과 실행

`VITE_SETTINGS_API=true`로 기존 /admin/standards/criteria와 /admin/standards/criteria/{setting_version_id}를 실제 조회에 연결한다. 운영자 화면의 실제 모드는 이 두 경로로 제한하며, 회차 선택·다른 운영 메뉴를 가짜 데이터와 혼합하지 않는다. 기존 AdminProvider의 회차 선행조건을 설정 조회 경로에서만 분리했다.

```powershell
# 저장소 루트: 개발 DB를 기존 RADAR_DB_*로 설정
uv run uvicorn app.main:app --port 8000
# frontend 폴더
$env:VITE_SETTINGS_API = 'true'
$env:VITE_I07_API = 'true'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm ci
npm run dev
```

두 플래그는 기본 false다. SETTINGS만 켜면 운영자 설정 조회, I07만 켜면 기존 city 승인 화면, 둘 다 켜면 각 역할의 화면을 사용한다. DB에 존재하는 개발 계정으로 로그인한다. flags가 바뀌면 개발 서버·빌드를 새로 시작한다. 캐시된 사용자 역할만 신뢰하지 않고 /api/auth/me와 각 API 권한을 확인한다. 세션 만료·조회 오류를 목업으로 우회하지 않는다.

## 이번 검증 증거

- I-02 HTTP/실제 SQL 방언 시험 12건 PASS, 영향받은 기존 I-07 HTTP 시험 39건 PASS. SQLite 방언 시험을 실제 MySQL 잠금 검증으로 부르지 않는다.
- Chromium 응답 제어 5시나리오 PASS: 목록/동일 이름의 다른 ID/상세 원문/돌려보냄 의견, 필터 빈 결과, 조회 오류, 만료 세션, 허용되지 않은 역할. script 문자열이 실행되지 않음을 확인했다.
- 실제 Chromium → 실제 FastAPI → 격리 MariaDB 10.11.14에서 운영자 조회 → 시 도로과 I-07 승인 → 운영자 재조회 1흐름 PASS. 실제 설정 2번은 승인·approved_by=22, 다른 설정·부서표는 제안 상태 유지, 87·88은 불변, 승인 감사 1건. 시험 DB를 정리했다. 산식·가중치 값은 만들지 않았다.
- 공통 인증 변경의 영향 범위로 기존 프론트 API 12건·DOM 7시나리오·I-07 Chromium 9항목 PASS와 기존 1024px TODO 1건을 확인했다. lint·기본 빌드·두 실제 플래그 빌드 PASS.

재현: 저장소 루트 `python -m pytest -q tests/test_settings_api.py tests/test_approvals_api.py`. 선택 브라우저 시험은 I07 문서의 외부 playwright-core·Chrome 실행 파일을 준비하고 `RADAR_I02_BROWSER_TEST=1`로 frontend에서 `npm run test:i02:browser`를 실행한다. 실제 DB/브라우저는 I07의 별도 로컬 시험 DB 환경을 설정하고 `uv run python tests/run_i07_live.py --browser --settings --output-dir <결과 디렉터리>`로 실행한다. 공용 DB를 사용하지 않는다.

## 통합과 미충족 조건

은경: 읽기 전용 API의 기존 DB·권한 계약 검토. 규림: AuthProvider·session·LoginPage·RequireOperator·AdminLayout·기존 기준 화면의 실제 모드 변경 검토. 진규: 병렬 1의 실제 산정 설정 형식과 로더 계약을 받은 뒤 생성·편집·사용 기록 연결. 팀원 담당을 이동하지 않는다.

main.py에는 SETTINGS와 기존 APPROVALS를 각각 한 번 등록한다. frontend/package.json은 시험 명령만 추가했고 의존성·package-lock.json·pyproject.toml·uv.lock은 바꾸지 않았다. 최신 core·llm 병합과 담당자 검토는 사용자 PC의 팀 저장소에서 이어간다. 전체 15개·70%·I-02 전체 완료·공식 정책 승인으로 판정하지 않는다.
