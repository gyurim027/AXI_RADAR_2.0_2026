"""AI-05 색인 만들기 — 원문 폴더 → 글자 뽑기 → 조문 자르기 → 색인 → 평가
사용 (저장소 루트에서):
  uv run python -m scripts.ai05_build_index <법령 원문 폴더> [기준일 YYYY-MM-DD]   # 원문부터 전부 다시
  uv run python -m scripts.ai05_build_index --from-chunks                          # data/ai05/chunks.jsonl로 색인만 다시
  uv run python -m scripts.ai05_build_index --add <새 원문 폴더> [기준일]           # 원문 몇 개만 더하기 (전체 원문 폴더 없이)
      새 원문 폴더도 국가법령정보센터_현행법령 / _행정규칙 / _자치법규 / 정책자료 하위 폴더 이름을 지킨다.
      같은 법령·시행일·별표 문서는 새 것으로 바꾸고, 없던 것은 docs.jsonl 끝에 더한다 (기존 조각 번호는 그대로).
법령이 개정되면(반기) 새 원문을 폴더에 넣고 첫 번째 명령을 다시 돌리면 됨.
원문 폴더는 저장소에 올리지 않음 (data/ai05에는 만든 결과만 둠)
"""
import datetime
import sys
from pathlib import Path

from app.services.ai05 import chunk, evaluate, extract
from app.services.ai05.rag import LawIndex

D = Path(__file__).resolve().parents[1] / "data" / "ai05"


def add_docs(src, today):
    """docs.jsonl에 새 원문만 더하고(같은 법령·시행일·별표면 바꿈) 조각을 다시 만든다."""
    import json
    docs = [json.loads(l) for l in open(D / "docs.jsonl", encoding="utf-8")]
    key = lambda d: (d["law_name"], d.get("effective"), d.get("annex"))
    pos = {key(d): i for i, d in enumerate(docs)}
    new = extract.read_folder(src)
    if not new:
        raise SystemExit(f"읽을 원문이 없습니다: {src} (하위 폴더 이름 확인)")
    for d in new:
        if d.get("error") or not d.get("chars"):
            print("  못 읽음:", d["file"], d.get("error", "글자 없음")); continue
        if key(d) in pos:
            docs[pos[key(d)]] = d; print("  바꿈:", d["law_name"], d.get("annex") or "")
        else:
            pos[key(d)] = len(docs); docs.append(d); print("  더함:", d["law_name"], d.get("annex") or "", d.get("effective") or "")
    with open(D / "docs.jsonl", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    chunk.main(D / "docs.jsonl", D / "chunks.jsonl", today)


def main(argv):
    D.mkdir(parents=True, exist_ok=True)
    if argv and argv[0] == "--add":
        if len(argv) < 2:
            raise SystemExit("--add 다음에 새 원문 폴더를 적어 주세요")
        today = argv[2] if len(argv) > 2 else datetime.date.today().isoformat()
        add_docs(argv[1], today)
    elif argv and argv[0] != "--from-chunks":
        src = argv[0]
        today = argv[1] if len(argv) > 1 else datetime.date.today().isoformat()
        extract.main(src, D / "docs.jsonl")                         # ① 원문 글자
        chunk.main(D / "docs.jsonl", D / "chunks.jsonl", today)    # ② 조문 조각 (기준일보다 시행일이 늦으면 '시행 전')
    LawIndex.build(D / "chunks.jsonl").save(D / "law_index.pkl")   # ③ 색인
    print("색인 저장 →", D / "law_index.pkl")
    evaluate.main(D / "law_index.pkl", D / "criterion.json", D / "eval_report.json")   # ④ 평가


if __name__ == "__main__":
    main(sys.argv[1:])
