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


class TaskFileTests(unittest.TestCase):
    def test_real_task_file(self):
        llm.load_tasks.cache_clear()
        conf = llm.load_tasks()
        self.assertEqual(conf["external_allowed"]["data_ids"], [])     # 처음에는 아무것도 외부로 안 보냄
        for name, t in conf["tasks"].items():
            self.assertIn(t.get("route"), llm.ROUTES, name)


if __name__ == "__main__":
    unittest.main()
