"""AI-07 로컬 연결 시험 서버. Python 표준 라이브러리만 사용합니다."""

import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from local_explainer import explain_frontend_candidate

SCHEMA = 'ai07.frontend-mock.v1'
MAX_BYTES = 64 * 1024


def require_text(value, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > 1500:
        raise ValueError('invalid_text')


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) != {'schema_version', 'data_kind', 'facts'}:
        raise ValueError('invalid_request')
    if payload['schema_version'] != SCHEMA or payload['data_kind'] != 'frontend_mock':
        raise ValueError('invalid_profile')
    facts = payload['facts']
    keys = {'runId', 'runName', 'gid', 'score', 'rank', 'evidence'}
    if not isinstance(facts, dict) or set(facts) != keys:
        raise ValueError('invalid_facts')
    for key in ('runId', 'runName', 'gid'):
        require_text(facts[key])
    score, rank = facts['score'], facts['rank']
    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError('invalid_score')
    if type(rank) is not int or not 1 <= rank <= 10000000:
        raise ValueError('invalid_rank')
    evidence = facts['evidence']
    if not isinstance(evidence, list) or len(evidence) > 50:
        raise ValueError('invalid_evidence')
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {'item', 'value', 'basisYear', 'source'}:
            raise ValueError('invalid_evidence')
        require_text(item['item'])
        require_text(item['value'], nullable=True)
        require_text(item['source'], nullable=True)
        year = item['basisYear']
        if year is not None and (type(year) is not int or not 1900 <= year <= 9999):
            raise ValueError('invalid_year')
    return facts


def explain_request(payload):
    facts = validate_request(payload)
    result = explain_frontend_candidate(facts)
    return {**result, 'schema_version': SCHEMA, 'data_kind': 'frontend_mock', 'facts': facts}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        # URL·입력·응답·예외 로그를 남기지 않는다.
        pass

    def safe_origin(self):
        port = self.server.server_address[1]
        if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            return False
        origin = self.headers.get('Origin')
        return origin is None or origin in {'http://127.0.0.1:5173', 'http://localhost:5173'}

    def respond(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.safe_origin():
            return self.respond(403, {'error': 'local_access_only'})
        if self.path == '/api/ai07/health':
            return self.respond(200, {'status': 'ok', 'external_api_called': False})
        self.respond(404, {'error': 'not_found'})

    def do_POST(self):
        self.connection.settimeout(5)
        if not self.safe_origin():
            return self.respond(403, {'error': 'local_access_only'})
        if self.path != '/api/ai07/explain':
            return self.respond(404, {'error': 'not_found'})
        if self.headers.get_content_type() != 'application/json':
            return self.respond(415, {'error': 'json_required'})
        if self.headers.get('Transfer-Encoding'):
            return self.respond(400, {'error': 'invalid_request'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.respond(400, {'error': 'invalid_request'})
        if length <= 0 or length > MAX_BYTES:
            return self.respond(413, {'error': 'invalid_size'})
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('invalid_size')
            payload = json.loads(raw)
            result = explain_request(payload)
        except (ValueError, TypeError, OverflowError, RecursionError):
            return self.respond(400, {'error': 'invalid_input'})
        except OSError:
            return self.respond(408, {'error': 'request_timeout'})
        except Exception:
            # 원본 입력이나 예외 상세를 응답에 포함하지 않는다.
            return self.respond(500, {'error': 'processing_failed'})
        self.respond(200, result)


def main():
    try:
        server = ThreadingHTTPServer(('127.0.0.1', 8007), Handler)
    except OSError:
        print('시작 실패: 8007 포트를 사용 중인지 확인해주세요.')
        return 1
    print('AI-07 Python 연결 서버: http://127.0.0.1:8007')
    print('외부 AI 호출 없음 / 요청·응답 본문 로그 없음 / 종료: Ctrl+C')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
