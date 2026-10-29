import csv
import re
from pathlib import Path

from app.core.llm import call_llm
from app.services.ai07.read_only_db import core_repository
from app.services.ai07.e03 import _canonical, JUDGMENT_STEMS

repo = core_repository()
run_id = 1

candidates = sorted(
    repo.candidates(run_id)["candidates"],
    key=lambda x: (x["rank_no"] is None, x["rank_no"] or 0)
)[:5]

results = []

for candidate in candidates:
    gid = candidate["gid"]
    data = repo.explanation(run_id, gid)

    if data["status"] != "ok":
        print("설명문 조회 실패:", gid)
        continue

    original = data["explanation"]

    response = call_llm(
        "ai07_explain",
        [
            {
                "role": "system",
                "content": (
                    "원본 설명문의 표현만 다듬으세요. "
                    "숫자, 순위, 격자 ID, 규칙 버전, 주의 문구를 변경하지 마세요. "
                    "새로운 사실이나 위험 판단을 추가하지 마세요. "
                    "다듬은 설명문만 출력하세요."
                ),
            },
            {"role": "user", "content": original},
        ],
    )

    proposal = response.text or ""
    errors = []

    if not response.ok:
        errors.append("llm_failed")

    if not isinstance(proposal, str) or not proposal.strip() or len(proposal) > 30000:
        errors.append("invalid_proposal")
    elif any(stem in proposal for stem in JUDGMENT_STEMS):
        errors.append("judgment_language")
    elif _canonical(proposal) != _canonical(original):
        errors.append("unsupported_change")

    accepted = not errors
    final_text = proposal if accepted else original

    results.append({
        "run_id": run_id,
        "gid": gid,
        "llm_ok": response.ok,
        "accepted": accepted,
        "refinement_status": "accepted" if accepted else "fallback",
        "validation_errors": "|".join(errors),
        "original_explanation": original,
        "ollama_proposal": proposal,
        "final_explanation": final_text,
        "original_restored": not accepted and final_text == original,
        "db_written": False,
    })

    print(
        f"격자 {gid}: "
        f"Ollama={'성공' if response.ok else '실패'}, "
        f"E-03={'수용' if accepted else '원문 복원'}, "
        f"오류={errors}"
    )

output = Path("outputs/ai07_eval/e03_real_db_final_5.csv")
output.parent.mkdir(parents=True, exist_ok=True)

if results:
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

print("\n평가 대상:", len(results))
print("수용:", sum(r["accepted"] for r in results))
print("원문 복원:", sum(not r["accepted"] for r in results))
print("결과 파일:", output)
print("DB 변경: 없음")
