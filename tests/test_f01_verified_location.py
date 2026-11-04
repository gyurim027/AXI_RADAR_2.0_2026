import unittest
import sys
import types
import importlib.util
from unittest.mock import patch, Mock
# This source ZIP contains only the standards subtree, not the live app.core.
# Use a no-network stand-in for local, isolated tests.
if importlib.util.find_spec('app.core') is None:
    core = types.ModuleType('app.core')
    core.db = types.ModuleType('app.core.db')
    core.db.read_only = Mock(side_effect=AssertionError('UNMOCKED_DB_READ'))
    sys.modules['app.core'] = core
    sys.modules['app.core.db'] = core.db
from app.services.standards.f01_verified_location import verified_advisory_gu


class VerifiedLocationTests(unittest.TestCase):
    ROW = {'gu': '분당구', 'lat': 37.4, 'lon': 127.1,
           'coord_method': '원본 좌표(본문 위치값)', 'coord_accuracy': '원본 좌표'}

    @patch('app.services.standards.f01_verified_location.db.read_only', return_value=[{'gu_center': '분당구'}])
    def test_agreement_only(self, query):
        r = verified_advisory_gu(self.ROW, gid='G1', table='src_complaint')
        self.assertEqual(r['gu'], '분당구')
        self.assertIn('warning', r)
        query.assert_called_once_with('SELECT gu_center FROM grid_cell WHERE gid = %s LIMIT 2', ('G1',))

    @patch('app.services.standards.f01_verified_location.db.read_only', return_value=[{'gu_center': '중원구'}])
    def test_mismatch_blocks(self, query):
        r = verified_advisory_gu(self.ROW, gid='G1', table='src_complaint')
        self.assertIsNone(r['gu'])
        self.assertEqual(r['reason'], 'SOURCE_GU_GRID_CENTER_MISMATCH')

    @patch('app.services.standards.f01_verified_location.db.read_only')
    def test_nonoriginal_geocode_blocks_without_query(self, query):
        for acc in ('보통', '낮음', '', None):
            self.assertIsNone(verified_advisory_gu({**self.ROW, 'coord_accuracy': acc}, gid='G1', table='src_complaint')['gu'])
        query.assert_not_called()

    @patch('app.services.standards.f01_verified_location.db.read_only')
    def test_road_hazard_not_automatically_routed(self, query):
        self.assertIsNone(verified_advisory_gu(self.ROW, gid='G1', table='src_road_hazard')['gu'])
        query.assert_not_called()

    @patch('app.services.standards.f01_verified_location.db.read_only')
    def test_missing_source_gu_blocks(self, query):
        self.assertIsNone(verified_advisory_gu({**self.ROW, 'gu': None}, gid='G1', table='src_complaint')['gu'])
        query.assert_not_called()

    @patch('app.services.standards.f01_verified_location.db.read_only', return_value=[])
    def test_missing_grid_row_blocks(self, query):
        self.assertIsNone(verified_advisory_gu(self.ROW, gid='G1', table='src_complaint')['gu'])

    @patch('app.services.standards.f01_verified_location.db.read_only')
    def test_no_source_location_invention(self, query):
        for row in [{**self.ROW, 'lat': None}, {**self.ROW, 'lon': 'x'}, {**self.ROW, 'coord_method': '주소 변환(지번 주소)'}]:
            self.assertIsNone(verified_advisory_gu(row, gid='G1', table='src_complaint')['gu'])
        query.assert_not_called()

if __name__ == '__main__':
    unittest.main()
