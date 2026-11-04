import unittest
from app.services.standards.f01_source_bridge import Candidate, jurisdiction_candidates

class Jur03Jur23RoutingTests(unittest.TestCase):
    def _route(self, kind, confirmed_id, blocked_id, blocked_has_dept=False, blocked_status='근거 없음'):
        c=Candidate('test-grid','src_complaint','test-source',kind,'source evidence','EXPLICIT_VERIFIED_KIND')
        jr=[{'jurisdiction_id':confirmed_id,'confirm_status':'확인됨','basis':'original verified source'}, {'jurisdiction_id':blocked_id,'confirm_status':blocked_status,'basis':''}]
        dr=[{'jurisdiction_id':confirmed_id,'dept_name':'EXISTING_CONFIRMED_DEPT','gu_name':'','condition_text':''}]
        if blocked_has_dept: dr.append({'jurisdiction_id':blocked_id,'dept_name':'REVIEW_DEPT','gu_name':'','condition_text':''})
        return jurisdiction_candidates(c,jr,dr,gu='수정구')

    def test_jur23_missing_dept_does_not_route_via_jur01(self):
        x=self._route('횡단보도','JUR-01','JUR-23')
        self.assertEqual(x['status'],'확인 필요')
        self.assertFalse(x['department_finalized'])
    def test_jur03_missing_dept_does_not_route_via_jur02(self):
        x=self._route('보도','JUR-02','JUR-03')
        self.assertEqual(x['status'],'확인 필요')
        self.assertFalse(x['department_finalized'])
    def test_jur23_unverified_even_with_dept(self):
        x=self._route('횡단보도','JUR-01','JUR-23',True)
        self.assertEqual(x['status'],'확인 필요')
    def test_jur03_unverified_even_with_dept(self):
        x=self._route('보도','JUR-02','JUR-03',True)
        self.assertEqual(x['status'],'확인 필요')
    def test_unrelated_single_confirmed_kind_remains_routable(self):
        c=Candidate('test-grid','src_complaint','test-source','조도','evidence','EXPLICIT_VERIFIED_KIND')
        x=jurisdiction_candidates(c,[{'jurisdiction_id':'JUR-05','confirm_status':'확인됨','basis':'verified'}],[{'jurisdiction_id':'JUR-05','dept_name':'LIGHTING','gu_name':'','condition_text':''}],gu='수정구')
        self.assertEqual(x['status'],'1차 부서 후보')

if __name__=='__main__': unittest.main()
