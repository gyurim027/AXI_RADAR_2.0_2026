"""공통 평가 틀 실행 (W05-06).

실행 (저장소 루트, PowerShell)
    uv run python -m scripts.eval_run --name ai05 --cases data/eval/ai05_cases.csv --adapter app.services.ai05.eval_adapter:run

- --cases   정답 목록 (CSV UTF-8 또는 xlsx). 칸: case_id · 입력 · 기대 답 · 맞음 기준 · 메모
- --adapter 각 기능의 '입력 → 결과' 함수 (모듈:함수)
- 결과 요약을 화면에 찍고, 자세한 결과는 out/eval/<이름>_<날짜>.json에 남긴다 (out/은 저장소에 올리지 않음)
- 기능별 실행 기록(85 job_run)은 남기지 않는다 (개발용 평가)
"""
from __future__ import annotations

import argparse
import sys

from app.services.evaluation.harness import evaluate, load_adapter, load_cases, save_report, summary_text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="RADAR 공통 평가 틀 (W05-06)")
    ap.add_argument("--name", required=True, help="기능 이름 (예: ai05, ai01, ai03)")
    ap.add_argument("--cases", required=True, help="정답 목록 파일")
    ap.add_argument("--adapter", required=True, help="예: app.services.ai05.eval_adapter:run")
    ap.add_argument("--min-rate", type=float, default=None, help="이 비율(%%)보다 낮으면 실패로 끝냄 (선택)")
    args = ap.parse_args(argv)

    rep = evaluate(args.name, load_cases(args.cases), load_adapter(args.adapter))
    print(summary_text(rep))
    print("자세한 결과:", save_report(rep))
    if args.min_rate is not None and rep.rate < args.min_rate:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
