"""서버 DB 조회 전용. 기존 가상자료 POST 서버와 별도로 실행합니다."""
from getpass import getpass
from urllib.parse import parse_qs, urlsplit
import re

from read_only_db import ReadOnlyRepository, make_connector
from server import Handler, ThreadingHTTPServer


def run_id_arg(query):
    values = query.get('run_id', [])
    if len(values) != 1 or not re.fullmatch(r'[0-9]{1,19}', values[0]):
        raise ValueError('invalid_run')
    if int(values[0]) > 9223372036854775807:
        raise ValueError('invalid_run')
    return values[0]


class DbHandler(Handler):
    def do_POST(self):
        self.respond(405, {'error': 'read_only_get_only'})

    def do_GET(self):
        if not self.safe_origin():
            return self.respond(403, {'error': 'local_access_only'})
        url = urlsplit(self.path)
        query = parse_qs(url.query, keep_blank_values=True)
        try:
            repo = self.server.repository
            if url.path == '/api/ai07/db/runs' and not query:
                result = repo.runs()
            elif url.path == '/api/ai07/db/candidates' and set(query) == {'run_id'}:
                result = repo.candidates(run_id_arg(query))
            elif url.path == '/api/ai07/db/explanation' and set(query) == {'run_id', 'gid'}:
                gids = query['gid']
                if len(gids) != 1 or not 1 <= len(gids[0]) <= 32:
                    raise ValueError('invalid_gid')
                result = repo.explanation(run_id_arg(query), gids[0])
            else:
                return self.respond(404, {'error': 'not_found'})
        except ValueError:
            return self.respond(400, {'error': 'invalid_input_or_stored_value'})
        except Exception:
            # 비밀번호·서버 오류 상세·SQL 본문·조회 결과를 출력하지 않는다.
            return self.respond(503, {'error': 'db_read_failed'})
        self.respond(200, result)


def main():
    print('AI-07 DB 읽기 전용 연결 / DB: mysqlteam02db')
    print('접속 정보는 이 PC 메모리에서만 사용하며 파일에 저장하지 않습니다.')
    try:
        host = input('HeidiSQL의 서버 주소: ').strip()
        port = int(input('포트 [3306]: ').strip() or '3306')
        user = input('DB 접속 아이디: ').strip()
        password = getpass('DB 비밀번호 (화면에 표시되지 않음): ')
        if not host or not user or not 1 <= port <= 65535:
            raise ValueError('invalid_connection')
        repo = ReadOnlyRepository(make_connector(host, port, user, password))
        # 인증·권한·읽기 전용 거래 지원을 확인한다. 실패하면 서버를 열지 않는다.
        snapshot = repo.runs()
    except ImportError:
        print('연결 도구가 없습니다. python -m pip install -r .\\requirements-db.txt 를 먼저 실행해주세요.')
        return 1
    except (EOFError, KeyboardInterrupt):
        print('\n종료했습니다.')
        return 0
    except Exception:
        print('DB 읽기 연결 실패. 서버 주소·포트·계정·권한·네트워크를 HeidiSQL 설정과 비교해주세요.')
        return 1
    try:
        http = ThreadingHTTPServer(('127.0.0.1', 8007), DbHandler)
    except OSError:
        print('8007 포트가 사용 중입니다. 이전 Python 시험 서버를 종료해주세요.')
        return 1
    http.repository = repo
    print('DB 읽기 연결 확인 / 조회한 실행 기록: ' + str(len(snapshot['runs'])) + '건 (최대 20건)')
    print('AI-07 DB 조회 서버: http://127.0.0.1:8007 / 종료: Ctrl+C')
    print('DB 변경 없음 / 외부 AI 호출 없음 / 요청·응답 본문 로그 없음')
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
