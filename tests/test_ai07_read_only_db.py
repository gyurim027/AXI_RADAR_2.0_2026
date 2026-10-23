from datetime import datetime
from decimal import Decimal
import unittest

# AI-07 원본 시험 (backend/ai07/test_read_only_db.py) — 공통 구조 경로로만 바꿈
from app.services.ai07.mock_input import run_id_arg
from app.services.ai07.read_only_db import ReadOnlyRepository, stored_explanation


def row(**patch):
    return {'run_id': 1, 'gid': 'SYNTHETIC-001', 'selected_yn': 'Y', 'score': Decimal('65.0000'),
            'rank_no': 2, 'build_id': 'SYNTHETIC', 'rule_version': 'SYNTHETIC-v1',
            'created_at': datetime(2026, 1, 1), **patch}


class FakeConnection:
    def __init__(self, records, fail=False):
        self.records = records
        self.fail = fail
        self.statements = []
        self.rolled_back = False
        self.closed = False

    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self, *_args): pass
    def execute(self, sql, args=()):
        self.statements.append((sql, args))
        if self.fail and sql.startswith('SELECT'):
            raise RuntimeError('synthetic test failure')
    def fetchall(self): return self.records
    def rollback(self): self.rolled_back = True
    def close(self): self.closed = True


class ReadOnlyTests(unittest.TestCase):
    def repo(self, rows, fail=False):
        conn = FakeConnection(rows, fail)
        return ReadOnlyRepository(lambda: conn), conn

    def assert_read_only(self, conn):
        self.assertEqual(conn.statements[0][0], 'START TRANSACTION READ ONLY')
        self.assertTrue(all(sql.startswith('SELECT') for sql, _ in conn.statements[1:]))
        self.assertTrue(conn.rolled_back)
        self.assertTrue(conn.closed)

    def test_empty_no_fake_result(self):
        repo, conn = self.repo([])
        result = repo.runs()
        self.assertEqual(result['status'], 'no_results')
        self.assertEqual(result['runs'], [])
        self.assert_read_only(conn)

    def test_score_precision_and_run_id(self):
        repo, conn = self.repo([row(run_id=9007199254740993)])
        result = repo.explanation('9007199254740993', 'SYNTHETIC-001')
        self.assertEqual(result['candidate']['score'], '65.0000')
        self.assertEqual(result['candidate']['run_id'], '9007199254740993')
        self.assertIn('65.0000점', result['explanation'])
        self.assert_read_only(conn)

    def test_missing_not_zero(self):
        repo, _ = self.repo([row(score=None)])
        result = repo.explanation('1', 'SYNTHETIC-001')
        self.assertEqual(result['status'], 'missing_values')
        self.assertIsNone(result['explanation'])
        self.assertIn('0.0000점', stored_explanation(row(score=Decimal('0.0000'))))

    def test_read_failure_rolls_back_closes(self):
        repo, conn = self.repo([], fail=True)
        with self.assertRaises(RuntimeError): repo.runs()
        self.assert_read_only(conn)

    def test_bound_parameters_and_no_dynamic_sql(self):
        repo, conn = self.repo([])
        gid = "SYNTHETIC' OR '1'='1"
        result = repo.explanation('1', gid)
        self.assertEqual(result['status'], 'not_found')
        sql, params = conn.statements[-1]
        self.assertNotIn(gid, sql)
        self.assertEqual(params, ('1', gid))
        self.assert_read_only(conn)

    def test_limit_and_invalid_stored_values(self):
        repo, conn = self.repo([row(gid=f'SYNTHETIC-{i}') for i in range(101)])
        result = repo.candidates('1')
        self.assertEqual(len(result['candidates']), 100)
        self.assertTrue(result['truncated'])
        self.assert_read_only(conn)
        for patch in ({'rank_no': 0}, {'score': Decimal('NaN')}, {'score': Decimal('101')}):
            with self.assertRaises(ValueError): stored_explanation(row(**patch))

    def test_request_validation(self):
        self.assertEqual(run_id_arg(['1']), '1')
        for values in ([], ['1', '2'], ['1 OR 1=1'], ['9223372036854775808']):
            with self.assertRaises(ValueError): run_id_arg(values)


if __name__ == '__main__': unittest.main()
