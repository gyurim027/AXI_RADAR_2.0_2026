from copy import deepcopy
from pathlib import Path
import json
import unittest
from app.services.ai07.f06 import build_request

class RequestTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).resolve().parents[1]/'samples/request.json').read_text(encoding='utf-8'))

    def test_normal_and_input_unchanged(self):
        before=deepcopy(self.data);r=build_request(self.data)
        self.assertEqual(r['status'],'draft');self.assertEqual(before,self.data)
        for token in ['65.0000점','2위','가상 담당 부서 A','근거 조문 확인 중','데이터로 모르는 것']:
            self.assertIn(token,r['request_text'])
        self.assertFalse(r['automatic_send']);self.assertFalse(r['llm_called']);self.assertFalse(r['db_written'])

    def test_unconfirmed_excluded_and_held_targets_blocked(self):
        for state in ['candidate','excluded','held',None]:
            with self.subTest(state=state):
                self.data['decision']['status']=state
                r=build_request(self.data)
                self.assertEqual(r['error_codes'],['target_not_confirmed']);self.assertIsNone(r['request_text'])

    def test_unknown_department_blocked(self):
        self.data['department']['status']='unknown'
        self.assertEqual(build_request(self.data)['error_codes'],['department_not_confirmed'])
        self.data['department']={'name':'확인 필요','status':'confirmed'}
        self.assertEqual(build_request(self.data)['status'],'blocked')

    def test_unreviewed_action_blocked(self):
        self.data['action']['review_status']='draft'
        self.assertEqual(build_request(self.data)['error_codes'],['action_not_reviewed'])

    def test_different_run_or_gid_blocked(self):
        for field in ['run_id','gid']:
            d=deepcopy(self.data);d['decision'][field]='OTHER'
            self.assertEqual(build_request(d)['error_codes'],['mixed_run_or_grid'])

    def test_law_requires_confirmation(self):
        self.data['laws']=[{'reference_id':'SYNTHETIC-LAW','title':'가상 기준','article':'제1조',
                           'text':'가상 조문 내용','review_status':'unconfirmed'}]
        self.assertEqual(build_request(self.data)['error_codes'],['law_not_confirmed'])
        self.data['laws'][0]['review_status']='confirmed'
        r=build_request(self.data)
        self.assertIn('가상 기준 제1조: 가상 조문 내용',r['request_text'])
        self.assertNotIn('근거 조문 확인 중',r['request_text'])

    def test_duplicate_law_reference_blocked(self):
        law={'reference_id':'SYNTHETIC-LAW','title':'가상 기준','article':'제1조','text':'가상 내용','review_status':'confirmed'}
        self.data['laws']=[law,deepcopy(law)]
        self.assertEqual(build_request(self.data)['error_codes'],['duplicate_law_reference'])

    def test_missing_card_values_not_zero(self):
        self.data['card']['score']=None;self.data['card']['rank']=None
        r=build_request(self.data)
        self.assertEqual(r['status'],'draft');self.assertIn('점수 모름, 순위 모름',r['request_text'])

    def test_bad_evidence_and_unknown_fields_blocked(self):
        self.data['card']['evidence'][0]['gid']='OTHER'
        self.assertEqual(build_request(self.data)['status'],'blocked')
        self.data['arbitrary_explanation']='점수는 99점'
        self.assertEqual(build_request(self.data)['error_codes'],['invalid_fields'])

    def test_actual_data_contract_rejected(self):
        self.data['data_kind']='actual'
        self.assertEqual(build_request(self.data)['error_codes'],['synthetic_contract_required'])

if __name__=='__main__':unittest.main()
