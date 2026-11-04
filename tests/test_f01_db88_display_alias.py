"""F-01 F-04 exact audited alias mapping safety tests (no DB/network)."""
import unittest
from app.services.standards.f01_db88_aliases import DB88_DISPLAY_ALIASES
from app.services.standards.f01_display_supply import load_display_sources
from app.services.standards.f04_department_contact import attach_department_contact


def apply(gu, dept, *, status='1차 부서 후보', matches=None):
    if matches is None:
        matches=[{'jurisdiction_id':'JUR-05'}]
    _, directory, _ = load_display_sources()
    return attach_department_contact(
        {'status':status,'receiving_dept':dept,'gu_name':gu,
         'matching_rules':matches, 'department_finalized':False},
        directory=directory)


class Db88DisplayAliasTests(unittest.TestCase):
    def test_all_explicit_aliases_are_uniquely_resolved(self):
        self.assertEqual(len(DB88_DISPLAY_ALIASES), 21)
        for (gu, dept), (g, canonical) in DB88_DISPLAY_ALIASES.items():
            with self.subTest(gu=gu, dept=dept):
                r=apply(gu,dept)
                self.assertEqual(r['contact_status'],'표시 가능')
                self.assertTrue(r['dept_phone'])
                self.assertEqual(r['contact_type'],'공식 업무분장상 팀장 직위 연락처')
                self.assertFalse(r['department_finalized'])

    def test_real_db_jur13_city_contact(self):
        r = apply(None, '시 도로과 도로행정팀(공유형 자전거·PM민원, 무단 방치자전거 관리)',
                  matches=[{'jurisdiction_id': 'JUR-13'}])
        self.assertEqual(r['contact_status'], '표시 가능')
        self.assertEqual(r['contact_type'], '공식 업무분장상 팀장 직위 연락처')
        self.assertTrue(r['contact_source_ref'])
        self.assertFalse(r['department_finalized'])

    def test_no_gu_crossover(self):
        # Similar names in multiple boroughs must never leak a phone.
        r=apply('수정구','분당구 건설과 도로조명팀')
        self.assertIsNone(r['dept_phone'])

    def test_no_fuzzy_or_substring_matching(self):
        r=apply('중원구','건설과 도로조명팀(다른 업무)')
        self.assertIsNone(r['dept_phone'])

    def test_nonexistent_db88_team_is_not_fabricated(self):
        self.assertNotIn(('분당구','경제교통과 교통행정팀'), DB88_DISPLAY_ALIASES)
        # A fabricated F-01 candidate cannot be validated by the directory alone.
        # The call site must pass ONLY an actual DB88-confirmed F-01 candidate.

    def test_unresolved_f01_is_not_enriched(self):
        r=apply('분당구','분당구 건설과 도로조명팀',status='확인 필요')
        self.assertIsNone(r['dept_phone'])

    def test_multiple_rules_are_not_enriched(self):
        r=apply('분당구','분당구 건설과 도로조명팀',matches=[{'jurisdiction_id':'JUR-05'},{'jurisdiction_id':'JUR-16'}])
        self.assertIsNone(r['dept_phone'])

    def test_unscoped_caller_cannot_get_borough_contact(self):
        r=apply(None,'건설과 도로관리팀')
        self.assertIsNone(r['dept_phone'])

    def test_original_exact_mapping_retained(self):
        r=apply('분당구','건설과 보도관리팀')
        self.assertEqual(r['dept_phone'],'031-729-7350')

    def test_no_f03_grade_inferred_from_contact(self):
        grades, _, state=load_display_sources()
        self.assertEqual(grades,{})
        self.assertIn('GRADE_UNVERIFIED',state)


if __name__ == '__main__':
    unittest.main()
