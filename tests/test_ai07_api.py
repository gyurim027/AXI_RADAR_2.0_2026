"""AI-07을 공통 서버에 붙인 뒤의 시험 (원래 backend/ai07/test_db_http.py·test_server.py 내용을 FastAPI로 옮김).
실제 DB 없이 돈다. 실행: uv run python -m unittest tests.test_ai07_api -v
"""
import copy
import json
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.ai07_explain_api import get_repository
from app.main import app
from app.services.ai07.local_explainer import explain_candidate
from app.services.ai07.mock_input import SCHEMA, explain_request
from app.services.ai07.read_only_db import envelope


def fixture():
    return {
        'schema_version': SCHEMA, 'data_kind': 'frontend_mock',
        'facts': {
            'runId': 'SYNTHETIC-RUN', 'runName': '가상 회차', 'gid': 'SYNTHETIC-001',
            'score': 65, 'rank': 2,
            'evidence': [{'item': '가상 항목', 'value': '0건', 'basisYear': 2025, 'source': '가상 출처'}],
        },
    }


class DbRouteTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock()
        self.repo.runs.return_value = envelope(status='no_results', runs=[], truncated=False)
        app.dependency_overrides[get_repository] = lambda: self.repo
        self.c = TestClient(app, base_url='http://127.0.0.1:8000')

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_read_routes_and_reject_writes(self):
        r = self.c.get('/api/ai07/db/runs')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'no_results')
        self.assertEqual(body['schemaVersion'], 'ai07.db-readonly.v1')          # 화면에는 camelCase
        self.assertFalse(body['externalApiCalled'])
        self.assertEqual(self.c.post('/api/ai07/db/runs').status_code, 405)
        self.assertEqual(self.c.get('/api/ai07/db/candidates?run_id=1%20OR%201=1').status_code, 400)
        self.assertEqual(self.c.get('/api/ai07/db/runs', headers={'Origin': 'https://example.invalid'}).status_code, 403)
        self.assertEqual(self.c.get('/api/ai07/db/execute?sql=DELETE').status_code, 404)
        self.assertEqual(self.c.get('/api/ai07/db/runs?extra=1').status_code, 404)
        self.assertEqual(self.repo.runs.call_count, 1)
        self.repo.candidates.assert_not_called()

    def test_snake_header_keeps_original_names(self):
        body = self.c.get('/api/ai07/db/runs', headers={'X-Response-Case': 'snake'}).json()
        self.assertIn('schema_version', body)

    def test_db_failure_hides_detail(self):
        self.repo.runs.side_effect = RuntimeError('password=SECRET sql=SELECT')
        r = self.c.get('/api/ai07/db/runs')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['error']['code'], 'db_read_failed')
        self.assertNotIn('SECRET', r.text)

    def test_explanation_arguments(self):
        self.repo.explanation.return_value = envelope(run_id='1', gid='G1', status='not_found', explanation=None)
        self.assertEqual(self.c.get('/api/ai07/db/explanation?run_id=1&gid=G1').status_code, 200)
        self.repo.explanation.assert_called_once_with('1', 'G1')
        self.assertEqual(self.c.get('/api/ai07/db/explanation?run_id=1&gid=' + 'x' * 33).status_code, 400)

    def test_other_host_rejected(self):
        other = TestClient(app, base_url='http://example.invalid')
        self.assertEqual(other.get('/api/ai07/health').status_code, 403)


class ExplainTests(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(app, base_url='http://127.0.0.1:8000')

    def post(self, body, ctype='application/json'):
        return self.c.post('/api/ai07/explain', content=body, headers={'Content-Type': ctype})

    def test_preserve_values(self):
        data = fixture()
        before = copy.deepcopy(data)
        result = explain_request(data)
        self.assertEqual(data, before)
        self.assertEqual(result['score_test'], 65)
        self.assertIn('65점이며, 현재 조회 범위의 순위는 2위', result['explanation'])

    def test_http_success_and_limits(self):
        r = self.post(json.dumps(fixture()))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['candidateId'], 'SYNTHETIC-001')
        bad = self.post('NOT_JSON_SYNTHETIC_MARKER')
        self.assertEqual(bad.status_code, 400)
        self.assertNotIn('SYNTHETIC_MARKER', bad.text)
        self.assertEqual(self.post('x' * 65537).status_code, 413)
        self.assertEqual(self.post('{}', 'text/plain').status_code, 415)

    def test_invalid_input(self):
        for patch in ({'score': True}, {'score': None}, {'score': float('nan')}, {'rank': 0}, {'extra': 'x'}):
            data = fixture()
            data['facts'].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                explain_request(data)

    def test_original_function_still_works(self):
        candidate = {'place': '독립 가상 장소', 'candidate_id': 'SYNTHETIC-002', 'score': 45, 'rank': 3, 'total': 10,
                     'contributions': {'가상 항목': 45}, 'complaint_included': False, 'formula_version': 'SYNTHETIC-v1'}
        self.assertIn('가상 항목 45점', explain_candidate(candidate)['explanation'])


if __name__ == '__main__':
    unittest.main()
