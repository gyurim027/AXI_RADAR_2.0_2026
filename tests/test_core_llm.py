"""공통 LLM 모듈(W05-05) 시험. 실제 모델 없이 가짜 응답으로 돈다.
실행: uv run python -m pytest tests/test_core_llm.py"""
import json
import logging
import unittest
from unittest import mock

from app.core import llm

SECRET = "주민등록번호-원문-테스트-문장"          # 로그에 나오면 안 되는 글자

TASKS = {
    "defaults": {"temperature": 0, "max_tokens": 100, "timeout_s": 5, "max_retries": 2, "json_retries": 1},
    "external_allowed": {"data_ids": ["DAT-OK"]},
    "tasks": {
        "t_internal": {"route": "internal", "model": "local-model"},
        "t_external": {"route": "external", "model": "cloud-model"},
        "t_no_model": {"route": "internal", "model": ""},
        "t_embed": {"route": "internal", "model": "embed-model"},
        "t_embed_external": {"route": "external", "model": "cloud-embed"},
        "t_embed_no_model": {"route": "internal", "model": ""},
    },
}
MSG = [{"role": "system", "content": "규칙"}, {"role": "user", "content": SECRET}]


class FakeProvider:
    """정해 둔 답이나 오류를 순서대로 돌려주는 가짜 제공자."""

    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def __call__(self, cfg, messages, want_json):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out, 10, 5


class LlmTests(unittest.TestCase):
    def setUp(self):
        llm.load_tasks.cache_clear()
        patches = [mock.patch.object(llm, "load_tasks", return_value=TASKS),
                   mock.patch.object(llm.time, "sleep"),
                   mock.patch.dict("os.environ", {"LLM_DEFAULT_ROUTE": "internal"})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_with(self, internal=None, external=None, **kw):
        internal = internal or FakeProvider()
        external = external or FakeProvider()
        with mock.patch.dict(llm.PROVIDERS, {"internal": internal, "external": external}):
            return llm.call_llm(kw.pop("task", "t_internal"), MSG, **kw), internal, external

    def test_unknown_task(self):
        r, _, _ = self.run_with(task="nope")
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, "unknown_task")

    def test_missing_model_is_config_error(self):
        r, i, _ = self.run_with(task="t_no_model")
        self.assertEqual(r.error_code, "config_error")
        self.assertEqual(i.calls, 0)

    def test_internal_ok(self):
        r, i, e = self.run_with(internal=FakeProvider("답"))
        self.assertTrue(r.ok)
        self.assertEqual((r.route, r.model, r.text), ("internal", "local-model", "답"))
        self.assertEqual((i.calls, e.calls), (1, 0))

    def test_external_blocked_when_raw_text(self):
        r, i, e = self.run_with(task="t_external", data_ids=["DAT-OK"], contains_raw=True)
        self.assertEqual(r.error_code, "external_not_allowed")
        self.assertEqual((i.calls, e.calls), (0, 0))        # 내부로 몰래 돌리지도 않음

    def test_external_blocked_when_raw_flag_missing(self):
        r, _, e = self.run_with(task="t_external", data_ids=["DAT-OK"])
        self.assertEqual(r.error_code, "external_not_allowed")
        self.assertEqual(e.calls, 0)

    def test_external_blocked_when_data_not_listed(self):
        for ids in ([], ["DAT-OK", "DAT-UNKNOWN"]):
            r, _, e = self.run_with(task="t_external", data_ids=ids, contains_raw=False)
            self.assertEqual(r.error_code, "external_not_allowed", ids)
            self.assertEqual(e.calls, 0)

    def test_external_allowed(self):
        r, _, e = self.run_with(task="t_external", external=FakeProvider("ok"), data_ids=["DAT-OK"], contains_raw=False)
        self.assertTrue(r.ok)
        self.assertEqual((r.route, e.calls), ("external", 1))

    def test_internal_down_does_not_go_external(self):
        r, i, e = self.run_with(internal=FakeProvider(llm.LlmError("internal_unavailable")))
        self.assertEqual(r.error_code, "internal_unavailable")
        self.assertEqual((i.calls, e.calls), (1, 0))

    def test_retry_then_ok(self):
        r, i, _ = self.run_with(internal=FakeProvider(llm.LlmError("timeout", retryable=True), "답"))
        self.assertTrue(r.ok)
        self.assertEqual((r.attempts, i.calls), (2, 2))

    def test_retry_gives_up(self):
        err = lambda: llm.LlmError("rate_limited", retryable=True)
        r, i, _ = self.run_with(internal=FakeProvider(err(), err(), err()))
        self.assertEqual((r.ok, r.error_code, i.calls), (False, "rate_limited", 3))   # 처음 1번 + 다시 2번

    def test_json_parse_and_retry(self):
        r, i, _ = self.run_with(internal=FakeProvider("형식 아님", '```json\n{"queries": ["a"]}\n```'),
                                response_format="json")
        self.assertTrue(r.ok)
        self.assertEqual(r.data, {"queries": ["a"]})
        self.assertEqual((i.calls, r.input_tokens), (2, 20))

    def test_json_gives_up(self):
        r, _, _ = self.run_with(internal=FakeProvider("x", "y"), response_format="json")
        self.assertEqual(r.error_code, "invalid_json")

    def test_log_has_no_content(self):
        with self.assertLogs("radar.llm", level=logging.INFO) as cm:
            self.run_with(internal=FakeProvider(SECRET + " 답"), request_id="rid-1")
        line = json.loads(cm.records[-1].getMessage())
        self.assertNotIn(SECRET, cm.output[-1])
        self.assertEqual(line["request_id"], "rid-1")
        self.assertEqual(set(line), {"ts", "request_id", "module", "task", "route", "model", "ok", "error_code",
                                     "attempts", "duration_ms", "input_tokens", "output_tokens"})

    def test_bad_messages(self):
        with self.assertRaises(ValueError):
            llm.call_llm("t_internal", [{"role": "user"}])


class OllamaBodyTests(unittest.TestCase):
    def test_keep_alive_sent(self):
        sent = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"message": {"content": "답"}}).encode("utf-8")

        def fake_urlopen(req, timeout):
            sent.update(json.loads(req.data.decode("utf-8")))
            return Resp()

        cfg = llm.TaskConfig("t", "internal", "local-model", 0, 10, 5, 0, 0, keep_alive="30m")
        with mock.patch.object(llm.urllib.request, "urlopen", fake_urlopen):
            llm._call_ollama(cfg, MSG, False)
        self.assertEqual(sent["keep_alive"], "30m")

    def test_think_sent_only_when_set(self):
        sent = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"message": {"content": "답"}}).encode("utf-8")

        def fake_urlopen(req, timeout):
            sent.clear()
            sent.update(json.loads(req.data.decode("utf-8")))
            return Resp()

        with mock.patch.object(llm.urllib.request, "urlopen", fake_urlopen):
            llm._call_ollama(llm.TaskConfig("t", "internal", "m", 0, 10, 5, 0, 0, think=False), MSG, False)
            self.assertIs(sent["think"], False)
            llm._call_ollama(llm.TaskConfig("t", "internal", "m", 0, 10, 5, 0, 0), MSG, False)
            self.assertNotIn("think", sent)

    def test_keep_alive_empty_not_sent(self):
        sent = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"message": {"content": "답"}}).encode("utf-8")

        def fake_urlopen(req, timeout):
            sent.update(json.loads(req.data.decode("utf-8")))
            return Resp()

        cfg = llm.TaskConfig("t", "internal", "local-model", 0, 10, 5, 0, 0)
        with mock.patch.object(llm.urllib.request, "urlopen", fake_urlopen):
            llm._call_ollama(cfg, MSG, False)
        self.assertNotIn("keep_alive", sent)


class FakeEmbedProvider:
    """정해 둔 숫자 묶음이나 오류를 순서대로 돌려주는 가짜 임베딩 제공자. 받은 글 목록을 기록한다."""

    def __init__(self, *outcomes):
        self.outcomes, self.calls, self.seen = list(outcomes), 0, []

    def __call__(self, cfg, texts):
        self.calls += 1
        self.seen.append(list(texts))
        out = self.outcomes.pop(0) if self.outcomes else [[0.1, 0.2] for _ in texts]
        if isinstance(out, Exception):
            raise out
        return out, 7


class EmbedTests(unittest.TestCase):
    def setUp(self):
        llm.load_tasks.cache_clear()
        patches = [mock.patch.object(llm, "load_tasks", return_value=TASKS),
                   mock.patch.object(llm.time, "sleep"),
                   mock.patch.dict("os.environ", {"LLM_DEFAULT_ROUTE": "internal"})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_with(self, provider=None, task="t_embed", texts=("보도의 너비", "인도 폭"), **kw):
        provider = provider or FakeEmbedProvider()
        with mock.patch.dict(llm.EMBED_PROVIDERS, {"internal": provider}):
            return llm.call_embed(task, list(texts), **kw), provider

    def test_ok_same_length_and_order(self):
        vecs = [[1.0, 0.0], [0.0, 1.0]]
        r, p = self.run_with(FakeEmbedProvider(vecs))
        self.assertTrue(r.ok)
        self.assertEqual((r.data, r.model, r.route, r.input_tokens), (vecs, "embed-model", "internal", 7))
        self.assertIsNone(r.text)
        self.assertEqual(p.seen, [["보도의 너비", "인도 폭"]])

    def test_unknown_task(self):
        r, p = self.run_with(task="nope")
        self.assertEqual((r.ok, r.error_code, p.calls), (False, "unknown_task", 0))

    def test_missing_model_is_config_error(self):
        r, p = self.run_with(task="t_embed_no_model")
        self.assertEqual((r.error_code, p.calls), ("config_error", 0))

    def test_external_route_is_never_sent(self):
        r, p = self.run_with(task="t_embed_external")
        self.assertEqual((r.ok, r.error_code, p.calls), (False, "config_error", 0))

    def test_internal_down_not_retried(self):
        r, p = self.run_with(FakeEmbedProvider(llm.LlmError("internal_unavailable")))
        self.assertEqual((r.error_code, p.calls), ("internal_unavailable", 1))

    def test_retry_then_ok(self):
        r, p = self.run_with(FakeEmbedProvider(llm.LlmError("timeout", retryable=True), [[1.0], [2.0]]))
        self.assertTrue(r.ok)
        self.assertEqual((r.attempts, p.calls), (2, 2))

    def test_retry_gives_up(self):
        err = lambda: llm.LlmError("timeout", retryable=True)
        r, p = self.run_with(FakeEmbedProvider(err(), err(), err()))
        self.assertEqual((r.ok, r.error_code, p.calls), (False, "timeout", 3))     # 처음 1번 + 다시 2번

    def test_bad_input_raises(self):
        for bad in ([], ["글", ""], ["글", "  "], ["글", 3], "글 하나", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                llm.call_embed("t_embed", bad)

    def test_log_has_no_text_or_vectors(self):
        with self.assertLogs("radar.llm", level=logging.INFO) as cm:
            self.run_with(FakeEmbedProvider([[0.123456, 0.2], [0.3, 0.4]]), texts=(SECRET, "질문"), request_id="rid-2")
        line = json.loads(cm.records[-1].getMessage())
        self.assertNotIn(SECRET, cm.output[-1])
        self.assertNotIn("0.123456", cm.output[-1])
        self.assertEqual((line["task"], line["request_id"], line["ok"]), ("t_embed", "rid-2", True))

    def test_caller_contract(self):
        """AI-05(app/services/ai05/embed.py)가 확인하는 모양: ok, data 개수 = 글 개수, model."""
        texts = ["a", "b", "c"]
        r, _ = self.run_with(texts=texts)
        self.assertTrue(getattr(r, "ok", False))
        self.assertIsInstance(r.data, list)
        self.assertEqual(len(r.data), len(texts))
        self.assertTrue(r.model)


class EmbedOllamaTests(unittest.TestCase):
    CFG = llm.TaskConfig("t", "internal", "m", 0, 10, 5, 0, 0, keep_alive="30m")

    def fake(self, reply):
        sent = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps(reply).encode("utf-8")

        def fake_urlopen(req, timeout):
            sent["url"] = req.full_url
            sent["body"] = json.loads(req.data.decode("utf-8"))
            return Resp()

        return sent, mock.patch.object(llm.urllib.request, "urlopen", fake_urlopen)

    def test_request_shape(self):
        sent, patch = self.fake({"model": "m", "embeddings": [[1, 2], [3.5, 4]], "prompt_eval_count": 9})
        with patch, mock.patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://pc:11434/"}):
            vecs, tokens = llm._embed_ollama(self.CFG, ["가", "나"])
        self.assertEqual(sent["url"], "http://pc:11434/api/embed")
        self.assertEqual(sent["body"], {"model": "m", "input": ["가", "나"], "keep_alive": "30m"})
        self.assertEqual((vecs, tokens), ([[1, 2], [3.5, 4]], 9))

    def test_keep_alive_empty_not_sent(self):
        sent, patch = self.fake({"embeddings": [[1.0]]})
        with patch:
            llm._embed_ollama(llm.TaskConfig("t", "internal", "m", 0, 10, 5, 0, 0), ["가"])
        self.assertNotIn("keep_alive", sent["body"])

    def test_bad_reply_shapes(self):
        for reply in ({}, {"embeddings": None}, {"embeddings": [[1.0]]}, {"embeddings": [[1.0], []]},
                      {"embeddings": [[1.0], ["x"]]}, {"embeddings": [[1.0], [True]]}):
            _, patch = self.fake(reply)
            with patch, self.assertRaises(llm.LlmError, msg=repr(reply)) as cm:
                llm._embed_ollama(self.CFG, ["가", "나"])
            self.assertEqual(cm.exception.code, "provider_error")


class TaskFileTests(unittest.TestCase):
    def test_real_task_file(self):
        llm.load_tasks.cache_clear()
        conf = llm.load_tasks()
        self.assertEqual(conf["external_allowed"]["data_ids"], [])     # 처음에는 아무것도 외부로 안 보냄
        for name, t in conf["tasks"].items():
            self.assertIn(t.get("route"), llm.ROUTES, name)

    def test_f05_and_ai05_tasks_registered(self):
        llm.load_tasks.cache_clear()
        tasks = llm.load_tasks()["tasks"]
        for name in ("f05_extract", "ai05_embed"):
            self.assertEqual(tasks[name]["route"], "internal", name)       # 공개 자료지만 내부 모델만
            self.assertTrue(tasks[name]["model"], name)
        self.assertEqual(llm.task_config("f05_extract").max_tokens, 400)


if __name__ == "__main__":
    unittest.main()
