"""공통 뼈대(W05-03) 시험. 실제 DB 없이 돈다. 실행: uv run python -m unittest tests.test_core -v"""
import unittest

from fastapi.testclient import TestClient

from app.core.responses import camelize, to_camel
from app.main import ROUTERS, app


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(app)

    def test_health_lists_modules(self):
        r = self.c.get('/health')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['modules'], [n for n, _ in ROUTERS])
        self.assertTrue(r.headers.get('X-Request-ID'))

    def test_routes_use_api_prefix(self):
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        for p in paths:
            if p not in ('/', '/health', '/health/db') and not p.startswith(('/docs', '/openapi', '/redoc')):
                self.assertTrue(p.startswith('/api/'), p)

    def test_camel_rules(self):
        self.assertEqual(to_camel('law_name'), 'lawName')
        self.assertEqual(to_camel('route'), 'route')            # 한 낱말은 그대로
        self.assertEqual(to_camel('근거_상태'), '근거_상태')       # 한글 키는 그대로
        self.assertEqual(to_camel('CK-09'), 'CK-09')            # 데이터 같은 키는 그대로
        self.assertEqual(camelize({'a_b': [{'c_d': 'e_f'}]}), {'aB': [{'cD': 'e_f'}]})   # 값은 안 바꿈

    def test_common_error_shape(self):
        r = self.c.get('/api/nothing-here')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['error']['code'], 'not_found')

    def test_cors_allows_front(self):
        r = self.c.options('/health', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'GET'})
        self.assertEqual(r.headers.get('access-control-allow-origin'), 'http://localhost:5173')
        r = self.c.options('/health', headers={'Origin': 'https://example.invalid', 'Access-Control-Request-Method': 'GET'})
        self.assertNotEqual(r.headers.get('access-control-allow-origin'), 'https://example.invalid')


if __name__ == '__main__':
    unittest.main()
