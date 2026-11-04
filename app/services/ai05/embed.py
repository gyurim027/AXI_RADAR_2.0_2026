"""AI-05 임베딩 검색 (기능정의서 v0.5.3 05_AI 기능 후보 AI-05: "임베딩: 한국어 임베딩 모델, 내부 실행").

공통 LLM 모듈(app/core/llm.py, W05-05 규림)의 임베딩 호출로만 부른다. AI-05가 모델을 직접 띄우지 않는다.
- 작업 이름: ai05_embed (llm_tasks.toml에 규림이 등록, route = "internal")
- 기대하는 공통 함수 (규림께 요청한 모양):
      call_embed(task, texts, *, request_id=None) -> LlmResult
      ok=True면 data = [[숫자, …], …] (texts와 같은 순서·같은 개수), model = 모델 이름
- 공통 모듈에 call_embed가 아직 없거나, 작업이 없거나(unknown_task), Ollama가 꺼져 있으면(internal_unavailable)
  임베딩 없이 지금까지의 낱말 검색(BM25)만 쓴다. 코드를 고치지 않아도 등록되면 켜진다.

넣는 글: 공개 법령 원문 조각과 검색 질문뿐 (민원·개인정보 없음). 외부로 보내지 않는다(내부 경로).

저장 파일 (data/ai05/, 저장소에 올리지 않음 — 공용 PC에서 scripts/ai05_build_embeddings로 만든다)
    embeddings.npy        조각마다 숫자 묶음 (float16, 길이 1로 맞춤)
    embeddings_meta.json  모델 이름 · 조각 수 · 조각 지문 · '못 찾음' 기준(sim_min) · 만든 날
조각(chunks.jsonl)이 바뀌어 지문이 다르면 옛 파일은 쓰지 않는다 (엉뚱한 조각을 가리키지 않게).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np

TASK = "ai05_embed"
TEXT_MAX = 1000          # 조각 글자를 이만큼만 넣음 (조문 한 조각은 대부분 이보다 짧다)
BATCH = 32               # 한 번에 보내는 조각 수 (공용 PC는 한 번에 하나씩 처리하므로 너무 크게 하지 않음)
SIM_MARGIN = 0.02        # '못 찾음' 기준 = 관계없는 질문(아래 두 묶음)의 가장 높은 유사도 + 이 값
# 법 냄새가 나지만 보행과 상관없는 질문 (10/26 조정: 법과 아주 먼 질문만으로 기준을 잡으면 '아파트 관리비 산정' 같은 질문을 못 거름)
# W05-06 20문항(data/eval/ai05_cases.csv)의 질문은 넣지 않는다 — 시험 문제로 기준을 맞추면 점수가 부풀려짐
HARD_NEGATIVE = ['상속세 신고 기한', '근로계약서 작성 의무', '전세 보증금 반환', '자동차 보험료 할인', '학교 급식 위생 기준',
                 '공무원 연금 수령 나이', '택배 분실 보상', '부동산 중개 수수료', '건강보험료 산정 방식', '반려동물 등록 방법']


def chunk_text(c: dict) -> str:
    return f"{c['law_name']} {c.get('article') or ''} {c.get('article_title') or c.get('section') or ''}\n{c['text']}"[:TEXT_MAX]


def fingerprint(chunks: list[dict]) -> str:
    """조각 목록의 지문 — 조각 번호·글자가 하나라도 바뀌면 달라진다."""
    h = hashlib.sha1()
    for c in chunks:
        h.update(f"{c['chunk_id']}\t{chunk_text(c)}\n".encode("utf-8"))
    return h.hexdigest()[:16]


def common_embedder(request_id: str | None = None):
    """공통 모듈의 call_embed를 감싼 함수(texts → (벡터 목록, 모델 이름))를 돌려준다. 쓸 수 없으면 (None, 이유)."""
    try:
        from app.core import llm
    except Exception as e:                                         # 공통 모듈을 못 읽으면 낱말 검색만
        return None, f"공통 LLM 모듈 없음 ({type(e).__name__})"
    call = getattr(llm, "call_embed", None)
    if call is None:
        return None, "공통 모듈에 임베딩 호출(call_embed) 없음"

    def run(texts: list[str]):
        res = call(TASK, texts, request_id=request_id)
        if not getattr(res, "ok", False):
            raise RuntimeError(getattr(res, "error_code", None) or "embed_failed")
        data = getattr(res, "data", None)
        if not isinstance(data, list) or len(data) != len(texts):
            raise RuntimeError("embed_bad_shape")
        return data, getattr(res, "model", None)
    return run, None


def _unit(m) -> np.ndarray:
    a = np.asarray(m, dtype=np.float32)
    n = np.linalg.norm(a, axis=-1, keepdims=True)
    return a / np.where(n == 0, 1, n)


def encode(texts: list[str], embedder, batch: int = BATCH):
    out, model = [], None
    for i in range(0, len(texts), batch):
        vecs, model = embedder(texts[i:i + batch])
        out.append(_unit(vecs))
    return (np.vstack(out) if out else np.zeros((0, 0), np.float32)), model


def build(chunks: list[dict], embedder, negatives: list[str], data_dir: Path) -> dict:
    """조각 전부를 숫자로 바꿔 저장하고, 관계없는 질문으로 '못 찾음' 기준(sim_min)을 정한다."""
    vecs, model = encode([chunk_text(c) for c in chunks], embedder)
    neg, _ = encode(list(negatives), embedder)
    sim_min = float((neg @ vecs.T).max()) + SIM_MARGIN if len(neg) else None
    data_dir = Path(data_dir)
    np.save(data_dir / "embeddings.npy", vecs.astype(np.float16))
    meta = {"task": TASK, "model": model, "chunks": len(chunks), "dim": int(vecs.shape[1]) if vecs.size else 0,
            "fingerprint": fingerprint(chunks), "sim_min": round(sim_min, 4) if sim_min is not None else None,
            "built_at": datetime.now().isoformat(timespec="seconds")}
    (data_dir / "embeddings_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def recalibrate(data_dir: Path, embedder, negatives: list[str]) -> dict:
    """임베딩을 다시 만들지 않고 '못 찾음' 기준(sim_min)만 다시 정해 embeddings_meta.json에 쓴다."""
    data_dir = Path(data_dir)
    vecs = np.load(data_dir / "embeddings.npy").astype(np.float32)
    neg, _ = encode(list(negatives), embedder)
    meta = json.loads((data_dir / "embeddings_meta.json").read_text(encoding="utf-8"))
    meta["sim_min"] = round(float((neg @ vecs.T).max()) + SIM_MARGIN, 4)
    meta["sim_min_from"] = f"관계없는 질문 {len(negatives)}개 + {SIM_MARGIN}"
    (data_dir / "embeddings_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def attach(ix, data_dir: Path, embedder=None) -> str:
    """저장해 둔 숫자 묶음을 색인(LawIndex)에 붙인다. 돌려주는 글은 /api/ai05/health의 '검색 방식' 칸."""
    data_dir = Path(data_dir)
    meta_p, vec_p = data_dir / "embeddings_meta.json", data_dir / "embeddings.npy"
    if not meta_p.exists() or not vec_p.exists():
        return "낱말 검색만 (임베딩 파일 없음)"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    if meta.get("chunks") != len(ix.C) or meta.get("fingerprint") != fingerprint(ix.C):
        return "낱말 검색만 (임베딩 파일이 지금 조각과 다름 → 다시 만들기)"
    if embedder is None:
        embedder, why = common_embedder()
        if embedder is None:
            return f"낱말 검색만 ({why})"
    ix.attach_embeddings(np.load(vec_p).astype(np.float32), lambda q: _unit(embedder([q])[0])[0], meta.get("sim_min"))
    return f"낱말 + 임베딩 ({meta.get('model')})"
