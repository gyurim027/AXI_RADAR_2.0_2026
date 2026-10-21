import copy
import http.client
import json
import threading
import unittest

from local_explainer import explain_candidate
from server import Handler, SCHEMA, ThreadingHTTPServer, explain_request


def fixture():
    return {
        'schema_version': SCHEMA, 'data_kind': 'frontend_mock',
        'facts': {
            'runId': 'SYNTHETIC-RUN', 'runName': '가상 회차', 'gid': 'SYNTHETIC-001',
            'score': 65, 'rank': 2,
            'evidence': [{'item': '가상 항목', 'value': '0건', 'basisYear': 2025, 'source': '가상 출처'}],
        },
    }


class ExplanationTests(unittest.TestCase):
    def test_preserve_values(self):
        data = fixture()
        before = copy.deepcopy(data)
        result = explain_request(data)
        self.assertEqual(data, before)
        self.assertEqual(result['facts'], data['facts'])
        self.assertEqual(result['score_test'], 65)
        self.assertFalse(result['external_api_called'])
        self.assertIn('65점이며, 현재 조회 범위의 순위는 2위', result['explanation'])
        self.assertIn('0건 (기준연도: 2025, 출처: 가상 출처)', result['explanation'])

    def test_nulls_and_zero(self):
        data = fixture()
        data['facts']['score'] = 0
        data['facts']['evidence'][0].update(value=None, basisYear=None, source=None)
        text = explain_request(data)['explanation']
        self.assertIn('0점', text)
        self.assertIn('확인할 수 없음 (기준연도: 미제공, 출처: 미제공)', text)

    def test_invalid_input(self):
        for patch in ({'score': True}, {'score': None}, {'score': float('nan')},
                      {'score': float('inf')}, {'rank': False}, {'rank': 0}, {'rank': 2.5},
                      {'evidence': 'wrong'}, {'extra': 'unexpected'}):
            data = fixture()
            data['facts'].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                explain_request(data)
        for patch in ({'data_kind': 'real'}, {'schema_version': 'other'}):
            with self.assertRaises(ValueError):
                explain_request({**fixture(), **patch})

    def test_original_function_still_works_with_synthetic_fixture(self):
        candidate = {'place': '독립 가상 장소', 'candidate_id': 'SYNTHETIC-002',
                     'score': 45, 'rank': 3, 'total': 10,
                     'contributions': {'가상 항목': 45}, 'complaint_included': False,
                     'formula_version': 'SYNTHETIC-v1'}
        result = explain_candidate(candidate)
        self.assertIn('전체 10개 격자', result['explanation'])
        self.assertIn('가상 항목 45점', result['explanation'])
        self.assertFalse(result['external_api_called'])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, body, headers=None, path='/api/ai07/explain'):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        conn.request('POST', path, body=body, headers={'Content-Type': 'application/json', **(headers or {})})
        response = conn.getresponse()
        result = response.status, response.read().decode('utf-8')
        conn.close()
        return result

    def test_loopback_success(self):
        status, body = self.request(json.dumps(fixture()))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['candidate_id'], 'SYNTHETIC-001')

    def test_bad_json_without_payload_echo(self):
        status, body = self.request('NOT_JSON_SYNTHETIC_MARKER')
        self.assertEqual(status, 400)
        self.assertNotIn('SYNTHETIC_MARKER', body)

    def test_other_origin_or_host_rejected(self):
        for headers in ({'Origin': 'https://example.invalid'}, {'Host': 'example.invalid'}):
            status, _ = self.request(json.dumps(fixture()), headers)
            self.assertEqual(status, 403)

    def test_limit_and_content_type(self):
        self.assertEqual(self.request('x' * 65537)[0], 413)
        self.assertEqual(self.request('{}', {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request('{}', path='/anything')[0], 404)


if __name__ == '__main__':
    unittest.main()
