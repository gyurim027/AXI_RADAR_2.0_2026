"""AI-05 임베딩 검색 시험 (실제 모델 없이 가짜 임베딩으로). 실행: uv run python -m pytest tests/test_ai05_embed.py

가짜 임베딩: 같은 뜻 낱말 묶음마다 칸 하나 (예: 인도·보도 → 0번 칸). 글자가 달라도 뜻이 같으면 가깝게 나온다.
실제 모델 품질은 공용 PC에서 scripts/ai05_build_embeddings로 확인한다.
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.services.ai05 import embed
from app.services.ai05.evaluate import NEGATIVE
from app.services.ai05.rag import NOT_FOUND, LawIndex

CONCEPTS = [("인도", "보도", "보행로"), ("너비", "유효폭", "넓이"), ("주차", "정차", "세워"), ("자전거",)]


def fake_vec(text):
    return [float(sum(text.count(w) for w in ws)) for ws in CONCEPTS]


def fake_embedder(texts):
    return [fake_vec(t) for t in texts], "fake-embed"


def chunk(i, law, art, text):
    return {"chunk_id": i, "law_name": law, "article": art, "text": text, "status": "시행 중", "cite": f"{law} {art}"}


CHUNKS = [chunk(1, "도로의 구조ㆍ시설 기준에 관한 규칙", "제16조", "보행로의 유효폭은 2미터 이상으로 하여야 한다."),
          chunk(2, "도로교통법", "제32조", "모든 차의 운전자는 교차로에 정차하거나 주차하여서는 아니 된다."),
          chunk(3, "자전거 이용 활성화에 관한 법률", "제3조", "자전거도로는 자전거 전용도로와 자전거 보행자 겸용도로로 구분한다.")]


def make(dir_):
    ix = LawIndex(CHUNKS)
    meta = embed.build(ix.C, fake_embedder, NEGATIVE, Path(dir_))
    return ix, meta


class EmbedSearchTests(unittest.TestCase):
    def test_finds_by_meaning_when_words_differ(self):
        with tempfile.TemporaryDirectory() as d:
            ix, meta = make(d)
            q = "걷는 길 넓이"                                       # 원문은 '보행로의 유효폭' — 낱말이 하나도 같지 않음
            self.assertEqual(ix.answer(query=q)["result"], NOT_FOUND)  # 낱말 검색만이면 못 찾음
            self.assertEqual(embed.attach(ix, Path(d), fake_embedder), "낱말 + 임베딩 (fake-embed)")
            r = ix.answer(query=q)
            self.assertEqual(r["result"], "찾음")
            self.assertEqual(r["items"][0]["cite"], "도로의 구조ㆍ시설 기준에 관한 규칙 제16조")
            self.assertEqual(r["items"][0]["quote"], CHUNKS[0]["text"])  # 원문 그대로 인용
            self.assertEqual(meta["chunks"], 3)

    def test_unrelated_question_still_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            ix, _ = make(d)
            embed.attach(ix, Path(d), fake_embedder)
            for q in ("김치찌개 끓이는 법", "프로야구 순위"):
                self.assertEqual(ix.answer(query=q)["result"], NOT_FOUND)

    def test_query_failure_falls_back_to_words(self):
        with tempfile.TemporaryDirectory() as d:
            ix, _ = make(d)
            embed.attach(ix, Path(d), fake_embedder)

            def down(texts):
                raise RuntimeError("internal_unavailable")
            ix._embed_query = lambda q: embed._unit(down([q])[0])[0]
            r = ix.search("교차로 정차 주차", k=3, min_score=0)      # 낱말 검색으로 찾는 질문 (조각 3개짜리 색인이라 점수 기준을 내림)
            self.assertEqual(r[0]["article"], "제32조")
            self.assertIsNone(r[0]["sim"])                             # 임베딩 없이 찾음


class AttachTests(unittest.TestCase):
    def test_no_files_or_changed_chunks(self):
        with tempfile.TemporaryDirectory() as d:
            ix = LawIndex(CHUNKS)
            self.assertEqual(embed.attach(ix, Path(d), fake_embedder), "낱말 검색만 (임베딩 파일 없음)")
            embed.build(CHUNKS[:2], fake_embedder, NEGATIVE, Path(d))   # 조각 2개로 만든 옛 파일
            self.assertIn("지금 조각과 다름", embed.attach(ix, Path(d), fake_embedder))
            self.assertIsNone(ix.emb)

    def test_common_module_without_call_embed(self):
        import app.core.llm as llm
        had = getattr(llm, "call_embed", None)
        if had is not None:
            del llm.call_embed
        try:
            fn, why = embed.common_embedder()
            self.assertIsNone(fn)
            self.assertIn("call_embed", why)
        finally:
            if had is not None:
                llm.call_embed = had

    def test_uses_common_module_result(self):
        import app.core.llm as llm
        had = getattr(llm, "call_embed", None)
        seen = {}

        def call_embed(task, texts, request_id=None):
            seen["task"] = task
            return SimpleNamespace(ok=True, model="fake-embed", data=[fake_vec(t) for t in texts])
        llm.call_embed = call_embed
        try:
            fn, why = embed.common_embedder()
            vecs, model = fn(["보도 너비"])
            self.assertEqual((seen["task"], model, vecs[0][:2]), ("ai05_embed", "fake-embed", [1.0, 1.0]))
            llm.call_embed = lambda *a, **k: SimpleNamespace(ok=False, error_code="unknown_task")
            fn, _ = embed.common_embedder()
            with self.assertRaises(RuntimeError):
                fn(["보도"])
        finally:
            if had is None:
                del llm.call_embed
            else:
                llm.call_embed = had


if __name__ == "__main__":
    unittest.main()
