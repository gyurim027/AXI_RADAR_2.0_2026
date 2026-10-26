# RADAR 2.0 — AI-10

AI-10은 CK-01~CK-14 **문제 유형별 조치 제안 문장 틀의 초안**을 Gemini로 생성하고, 운영자 검토·승인 후 승인 문장을 재사용하는 기능입니다. 후보별 위험도 판정, 현장 사실 확인, 법령 확정, 실제 DB 구축은 이 모듈의 역할이 아닙니다.

## 프로젝트 구성

| 경로 | 역할 |
|---|---|
| `app/services/` | 최신 AI-10 생성·검증·검토·문장 조합·81/82번 매핑 구현 |
| `app/api/ai10_review_api.py` | 검토·승인·조회 개발용 API |
| `app/main.py` | FastAPI 앱 및 라우터 |
| `data/ai10_ck_rules_v0.4.1.json` | **최신 CK 기준** |
| `data/ai10_operator_review_dev.json` | 개발용 문장 검토 상태. 운영 DB 아님 |
| `tests/` | 자동 검증 스크립트 |
| `reports/` | Gemini 시험 및 이전·최신 문장 비교 기록 |
| `RADAR_AI10_기능 구현·검증 결과 및 팀 통합 인계서.md` | 검증 이력, DB/API 연동 조건, 미완료 사항 상세 |

## 실행 전

프로젝트 루트에 기존 Python/uv 가상환경 및 의존성이 구성되어 있어야 합니다. 실제 Gemini 생성 시 로컬 `.env`에 `GEMINI_API_KEY`와 `GEMINI_MODEL`이 필요합니다. **`.env`와 인증키는 ZIP/저장소에 포함하거나 팀 채팅에 게시하지 마세요.**

아래 명령은 프로젝트 루트에서 Windows PowerShell 기준입니다.

```powershell
cd C:\kimdaehwan\radar-ai10-action
$env:PYTHONPATH = (Get-Location).Path

# 실제 Gemini 호출 없이 CK-03의 프롬프트만 확인
uv run python app/services/ai10_draft.py CK-03

# 실제 Gemini 호출: 초안 생성만 수행, 승인/운영 DB 저장 안 함
uv run python app/services/ai10_draft.py CK-03 --generate
```

## 핵심 회귀시험

```powershell
$tests = @(
  'test_ai10_draft_retry_v052.py',
  'test_ai10_review_api_v052.py',
  'test_ai10_operator_review_v052.py',
  'test_ai10_review_api_regression_v052.py',
  'test_ai10_approved_template_v052.py',
  'test_ai10_action_proposal.py',
  'test_ai10_action_template_mapping.py',
  'test_ai10_candidate_action_mapping.py',
  'test_ai10_latest_full_flow_v052.py'
)
foreach ($test in $tests) {
  uv run python "tests\$test"
  if ($LASTEXITCODE -ne 0) { throw "시험 실패: $test" }
}
```

2026-10-19 사용자 PC에서 정리본 적용 후 **9개 시험 파일 통과, 실패 0** 확인. 해당 시험은 운영 DB 연동·실계정 승인·실제 화면 연결 시험이 아닙니다.

## 실제 민원 16건 비교 재실행 (Gemini 호출)

```powershell
uv run python tests/test_ai10_complaint_latest_compare_v052.py --all --generate
```

결과는 `reports/ai10_민원16건_구버전대비_최신생성_비교_v052.json`에 기록합니다. 기존 연결 기준에서는 16건 중 CK-14 잠정 연결 3건에 **공통 유형 문장을 1회 생성**하고, 13건은 CK 미연결로 남았습니다. 실제 민원별 CK 판정/최종 승인이 아닙니다.

## 팀 통합 시 주의

- 운영자 원문 대조 및 승인 전에는 문장을 업무에 적용하지 않습니다.
- 81번 `action_template`과 82번 `priority_candidate_action`의 실제 DB 읽기·쓰기는 아직 연결되지 않았습니다.
- 82번에는 실제 선정 후보, 확인된 CK·담당 부서·법령 근거가 필요합니다. 근거를 추정해 채우지 않습니다.
- `AI10_DEV_API_ENABLED=1`은 개발용 쓰기 허용 옵션이지 운영 인증·인가가 아닙니다.
- 세부 명세·시험 기록·팀별 책임 분리는 **「RADAR 2.0 — AI-10 기능 구현·검증 결과 및 팀 통합 인계서」**에서 확인하세요.
