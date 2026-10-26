"""AI-05 임베딩 조정 (docs/ai05/embedding.md '점수가 낮을 때 고치는 순서' 2번).

이미 만든 임베딩(data/ai05/embeddings.npy)으로, 섞는 방법을 바꿔 가며 점수를 비교한다. 임베딩을 다시 만들지 않는다.
바꿔 보는 것
  - EMB_W        임베딩 순위의 무게 (낱말 순위 = 1)
  - '못 찾음' 기준  관계없는 질문의 가장 높은 유사도 + 여유(margin). 관계없는 질문은 두 묶음 중 고름
        기본  : evaluate.NEGATIVE (점심 메뉴·야구처럼 법과 아주 먼 질문 10개) — 지금 embeddings_meta.json의 sim_min
        법률형: HARD_NEGATIVE (상속세·전세 보증금처럼 법 냄새가 나지만 보행과 상관없는 질문 10개)
  20문항 정답 목록(data/eval/ai05_cases.csv)의 질문은 기준을 정하는 데 쓰지 않는다 (시험 문제로 기준을 맞추면 점수가 부풀려짐).

실행 (저장소 루트, .env OLLAMA_BASE_URL이 Ollama를 가리킬 때)
    uv run python -m scripts.ai05_tune_embeddings
질문마다 임베딩은 한 번만 부르고 기억해 둔다 (조합이 많아도 Ollama 호출은 질문 수만큼).
결과: 화면에 표 + out/ai05/embed_tune_<날짜>.json. 고른 값은 은경이 rag.py(EMB_W)·embed.py(SIM_MARGIN, 기준 질문 묶음)에 반영.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from app.services.ai05 import embed, evaluate
from app.services.ai05.service import LawService
from scripts.ai05_build_embeddings import CASES, D, ROOT

HARD_NEGATIVE = embed.HARD_NEGATIVE
EMB_WS = (0.5, 1.0, 1.5)
MARGINS = (0.0, 0.02, 0.05, 0.08)


def main() -> int:
    embedder, why = embed.common_embedder()
    if embedder is None:
        print("임베딩을 쓸 수 없어 멈춥니다:", why)
        return 1
    svc = LawService()
    if svc.ix.emb is None:
        print("임베딩 파일이 없습니다. 먼저 uv run python -m scripts.ai05_build_embeddings 를 돌려 주세요:", svc.search_mode)
        return 1
    ix = svc.ix
    cache: dict[str, np.ndarray] = {}

    def qvec(q: str) -> np.ndarray:                      # 질문마다 한 번만 Ollama를 부름
        if q not in cache:
            cache[q] = embed._unit(embedder([q])[0])[0]
        return cache[q]
    ix._embed_query = qvec

    def top_sim(qs):
        return max(float((ix.emb @ qvec(q)).max()) for q in qs)
    base = {"기본": top_sim(evaluate.NEGATIVE), "법률형": top_sim(HARD_NEGATIVE)}

    from scripts.ai05_build_embeddings import harness_run
    rows = json.load(open(D / "criterion.json", encoding="utf-8"))
    emb, results = ix.emb, []
    ix.emb = None
    words = {"색인": evaluate.brief(evaluate.run(ix, rows)), "20문항": harness_run(svc)}
    ix.emb = emb
    for neg, b in base.items():
        for m in MARGINS:
            for w in EMB_WS:
                ix.sim_min, ix.EMB_W = b + m, w
                r = {"기준 질문": neg, "margin": m, "EMB_W": w, "sim_min": round(b + m, 4),
                     "색인": evaluate.brief(evaluate.run(ix, rows)), "20문항": harness_run(svc)}
                results.append(r)

    def line(name, r):
        s, t = r["색인"]["B_검색"], r["20문항"]
        return (f"{name:<28} 20문항 {t['통과']:>5} 오연결 {str(t['오연결률']):>5}% · 1등 {s['1등 정답']:.3f} · 5등 안 {s['5등 안 정답']:.3f}"
                f" · 못찾음 {r['색인']['C_못찾음']['못 찾음으로 나옴']:.1f} · 틀린 문제 {','.join(t['틀린 문제'])}")
    print(line("낱말 검색만", words))
    for r in results:
        print(line(f"{r['기준 질문']} +{r['margin']:.2f} · W{r['EMB_W']}", r))

    def key(r):                                          # 20문항 통과 → 오연결 낮음 → 5등 안 → 1등
        p = int(r["20문항"]["통과"].split("/")[0])
        return (p, -(r["20문항"]["오연결률"] or 0), r["색인"]["B_검색"]["5등 안 정답"], r["색인"]["B_검색"]["1등 정답"])
    best = max(results, key=key)
    print("\n추천:", f"기준 질문 {best['기준 질문']} · margin {best['margin']} · EMB_W {best['EMB_W']} (sim_min {best['sim_min']})")
    w_pass = int(words["20문항"]["통과"].split("/")[0])
    if key(best)[0] < w_pass:
        print("※ 어떤 조합도 20문항이 낱말 검색만보다 낮습니다 → 다음 순서(다른 모델로 바꾸기)를 검토하세요.")
    out = ROOT / "out" / "ai05"
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"embed_tune_{datetime.now():%Y%m%d_%H%M}.json"
    p.write_text(json.dumps({"낱말 검색만": words, "기준 유사도": base, "조합": results, "추천": best},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    print("자세한 결과:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
