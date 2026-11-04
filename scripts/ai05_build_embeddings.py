"""AI-05 임베딩 만들기와 전후 비교 (공용 PC에서 실행).

실행 (저장소 루트, PowerShell) — .env의 OLLAMA_BASE_URL이 공용 PC를 가리키고, 규림님이 공통 모듈에
call_embed와 llm_tasks.toml [tasks.ai05_embed]를 넣은 뒤에 돈다.
    uv run python -m scripts.ai05_build_embeddings              # 만들기 + 비교
    uv run python -m scripts.ai05_build_embeddings --compare    # 이미 만든 파일로 비교만
    uv run python -m scripts.ai05_build_embeddings --recalibrate  # 임베딩은 그대로, '못 찾음' 기준만 다시 정하고 비교

하는 일
1) 법령 조각(data/ai05/chunks → law_index.pkl의 조각 약 3,400개)을 공통 모듈로 숫자 묶음으로 바꿔 data/ai05/embeddings.npy에 저장
2) 관계없는 질문 10개로 '못 찾음' 기준(sim_min)을 정해 embeddings_meta.json에 저장
3) 같은 질문을 '낱말 검색만'과 '낱말 + 임베딩'으로 돌려 비교
   - 색인 자체 평가 (법령색인 정답: 1등 정답 · 5등 안 정답 · 관계없는 질문 걸러냄)
   - 공통 평가 틀 W05-06 20문항 (data/eval/ai05_cases.csv)
결과 요약은 화면에, 자세한 결과는 out/ai05/embed_compare_<날짜>.json (out/은 저장소에 올리지 않음)

넣는 글은 공개 법령 원문과 질문뿐이다 (민원·개인정보 없음). embeddings.* 파일은 저장소에 올리지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from app.services.ai05 import embed, evaluate
from app.services.ai05.service import LawService

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "ai05"
CASES = ROOT / "data" / "eval" / "ai05_cases.csv"


def harness_run(svc: LawService):
    from app.services.evaluation.harness import evaluate as ev, load_cases
    from app.services.ai05.eval_adapter import TYPE_CODE

    def fn(text: str, k: int = 5):
        text = (text or "").strip()
        r = svc.related_articles(text, None, k, False) if TYPE_CODE.match(text) else svc.related_articles(None, text, k, False)
        return [it["cite"] for it in r.get("items", [])]
    rep = ev("ai05", load_cases(CASES), fn)
    return {"통과": f"{rep.passed}/{rep.total}", "오연결률": rep.wrong_link_rate, "찾은 비율": rep.find_rate,
            "틀린 문제": [f["case_id"] for f in rep.failed]}


def compare(svc: LawService) -> dict:
    rows = json.load(open(D / "criterion.json", encoding="utf-8"))
    emb = svc.ix.emb
    svc.ix.emb = None                                        # 낱말 검색만
    before = {"색인 평가": evaluate.brief(evaluate.run(svc.ix, rows)), "20문항": harness_run(svc)}
    svc.ix.emb = emb                                         # 낱말 + 임베딩
    after = {"색인 평가": evaluate.brief(evaluate.run(svc.ix, rows)), "20문항": harness_run(svc)}
    return {"낱말 검색만": before, "낱말 + 임베딩": after}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AI-05 임베딩 만들기·비교")
    ap.add_argument("--compare", action="store_true", help="만들지 않고 비교만")
    ap.add_argument("--recalibrate", action="store_true", help="임베딩은 그대로 두고 '못 찾음' 기준만 다시 정한 뒤 비교")
    args = ap.parse_args(argv)

    embedder, why = embed.common_embedder()
    if embedder is None:
        print("임베딩을 쓸 수 없어 멈춥니다:", why)
        print("→ 규림님 공통 모듈에 call_embed와 [tasks.ai05_embed]가 들어갔는지, .env OLLAMA_BASE_URL을 확인하세요.")
        return 1
    svc = LawService()
    negatives = list(evaluate.NEGATIVE) + list(embed.HARD_NEGATIVE)
    if args.recalibrate:
        meta = embed.recalibrate(D, embedder, negatives)
        print("'못 찾음' 기준 다시 정함:", meta["sim_min"], meta["sim_min_from"])
    elif not args.compare:
        print(f"조각 {len(svc.ix.C)}개를 숫자로 바꾸는 중 (공용 PC 상태에 따라 몇 분 걸릴 수 있음)…")
        meta = embed.build(svc.ix.C, embedder, negatives, D)
        print("저장:", D / "embeddings.npy", json.dumps(meta, ensure_ascii=False))
    svc.search_mode = embed.attach(svc.ix, D, embedder)
    print("검색 방식:", svc.search_mode)
    if svc.ix.emb is None:
        return 1
    res = compare(svc)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    out = ROOT / "out" / "ai05"
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"embed_compare_{datetime.now():%Y%m%d_%H%M}.json"
    p.write_text(json.dumps({"검색 방식": svc.search_mode, **res}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("자세한 결과:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
