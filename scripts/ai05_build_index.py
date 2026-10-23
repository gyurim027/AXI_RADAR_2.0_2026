"""AI-05 색인 만들기 — 원문 폴더 → 글자 뽑기 → 조문 자르기 → 색인 → 평가
사용 (저장소 루트에서):
  uv run python -m scripts.ai05_build_index <법령 원문 폴더> [기준일 YYYY-MM-DD]   # 원문부터 전부 다시
  uv run python -m scripts.ai05_build_index --from-chunks                          # data/ai05/chunks.jsonl로 색인만 다시
법령이 개정되면(반기) 새 원문을 폴더에 넣고 첫 번째 명령을 다시 돌리면 됨.
원문 폴더는 저장소에 올리지 않음 (data/ai05에는 만든 결과만 둠)
"""
import datetime
import sys
from pathlib import Path

from app.services.ai05 import chunk, evaluate, extract
from app.services.ai05.rag import LawIndex

D = Path(__file__).resolve().parents[1] / "data" / "ai05"


def main(argv):
    D.mkdir(parents=True, exist_ok=True)
    if argv and argv[0] != "--from-chunks":
        src = argv[0]
        today = argv[1] if len(argv) > 1 else datetime.date.today().isoformat()
        extract.main(src, D / "docs.jsonl")                         # ① 원문 글자
        chunk.main(D / "docs.jsonl", D / "chunks.jsonl", today)    # ② 조문 조각 (기준일보다 시행일이 늦으면 '시행 전')
    LawIndex.build(D / "chunks.jsonl").save(D / "law_index.pkl")   # ③ 색인
    print("색인 저장 →", D / "law_index.pkl")
    evaluate.main(D / "law_index.pkl", D / "criterion.json", D / "eval_report.json")   # ④ 평가


if __name__ == "__main__":
    main(sys.argv[1:])
