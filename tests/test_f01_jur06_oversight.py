"""Isolated regression checks for the exact JUR-06 city-oversight distinction."""
import unittest
from app.services.standards.f01_source_bridge import Candidate, jurisdiction_candidates


class Jur06OversightTests(unittest.TestCase):
    def setUp(self):
        self.c = Candidate('G1', 'src_complaint', 'C1', '주정차', '불법 주정차', 'EXPLICIT_REPORT_TYPE')
        self.j = [{'jurisdiction_id': 'JUR-06', 'basis': 'DB87', 'confirm_status': '확인됨'}]
        self.city = {'jurisdiction_id': 'JUR-06', 'gu_name': None,
                     'dept_name': '시 교통기획과 교통지도팀(단속 업무지도)', 'condition_text': None}
        self.district = {'jurisdiction_id': 'JUR-06', 'gu_name': '분당구',
                         'dept_name': '분당구 경제교통과 주차관리팀(동별 배정)', 'condition_text': None}

    def route(self, rows, **kwargs):
        return jurisdiction_candidates(self.c, self.j, rows, **kwargs)

    def test_one_district_handler_with_city_oversight(self):
        r = self.route([self.city, self.district], gu='분당구')
        self.assertEqual(r['status'], '1차 부서 후보')
        self.assertEqual(len(r['candidate_departments']), 1)
        self.assertEqual(r['candidate_departments'][0]['dept_name'], self.district['dept_name'])
        self.assertIn('CITY_OVERSIGHT_NOT_FIRST_LINE_HANDLER',
                      [x['reason'] for x in r['blocked_conditions']])
        self.assertFalse(r['department_finalized'])

    def test_no_district_handler_is_not_invented(self):
        r = self.route([self.city], gu='분당구')
        self.assertEqual(r['status'], '확인 필요')
        self.assertEqual(r['candidate_departments'], [])

    def test_gu_unknown_blocks_district(self):
        r = self.route([self.city, self.district], gu=None)
        self.assertEqual(r['status'], '확인 필요')
        self.assertEqual(r['candidate_departments'], [])

    def test_wrong_gu_blocks_district(self):
        r = self.route([self.city, self.district], gu='수정구')
        self.assertEqual(r['status'], '확인 필요')
        self.assertEqual(r['candidate_departments'], [])

    def test_two_district_rows_remain_ambiguous(self):
        r = self.route([self.city, self.district, {**self.district, 'dept_name':'분당구 경제교통과 주차관리팀(지도·단속·과태료·안전신문고 처리)'}], gu='분당구')
        self.assertEqual(r['status'], '확인 필요')
        self.assertEqual(len(r['candidate_departments']), 2)

    def test_city_not_excluded_for_other_jurisdiction(self):
        c = Candidate('G1', 'src_complaint', 'C1', '적치', '불법 적치', 'EXPLICIT_REPORT_TYPE')
        j = [{'jurisdiction_id': 'JUR-07', 'basis': 'DB87', 'confirm_status':'확인됨'}]
        row = {**self.city, 'jurisdiction_id': 'JUR-07'}
        r = jurisdiction_candidates(c, j, [row], gu='분당구')
        self.assertEqual(r['status'], '1차 부서 후보')

    def test_conditional_district_does_not_bypass_f02(self):
        r = self.route([self.city, {**self.district, 'condition_text': '특정 동'}], gu='분당구')
        self.assertEqual(r['status'], '확인 필요')
        self.assertEqual(r['candidate_departments'], [])

if __name__ == '__main__':
    unittest.main()
