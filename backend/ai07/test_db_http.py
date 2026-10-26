import http.client
import json
import threading
import unittest
from unittest.mock import Mock
from db_server import DbHandler, ThreadingHTTPServer
from read_only_db import envelope


class DbHttpTests(unittest.TestCase):
    def test_read_routes_and_reject_writes(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), DbHandler)
        repo = Mock()
        repo.runs.return_value = envelope(status='no_results', runs=[])
        server.repository = repo
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(method, path, headers=None):
                conn = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=3)
                conn.request(method, path, headers=headers or {})
                response = conn.getresponse()
                result = response.status, json.loads(response.read())
                conn.close()
                return result
            status, body = request('GET', '/api/ai07/db/runs')
            self.assertEqual(status, 200)
            self.assertEqual(body['status'], 'no_results')
            self.assertEqual(request('POST', '/api/ai07/db/explain')[0], 405)
            self.assertEqual(request('GET', '/api/ai07/db/candidates?run_id=1%20OR%201=1')[0], 400)
            self.assertEqual(request('GET', '/api/ai07/db/runs', {'Origin': 'https://example.invalid'})[0], 403)
            self.assertEqual(request('GET', '/api/ai07/db/execute?sql=DELETE')[0], 404)
            self.assertEqual(repo.runs.call_count, 1)
            repo.candidates.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
