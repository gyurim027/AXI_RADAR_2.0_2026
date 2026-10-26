from copy import deepcopy
import json
from pathlib import Path
import unittest
from app.services.ai07.h04 import build_report,HEADINGS

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).resolve().parents[1]/'samples/report.json').read_text(encoding='utf-8'))

    def test_sections_counts_and_no_mutation(self):
        original=deepcopy(self.data);r=build_report(self.data)
        self.assertEqual(r['status'],'draft');self.assertEqual(self.data,original)
        self.assertEqual([s['title'] for s in r['sections']],list(HEADINGS))
        self.assertEqual([s['candidate_count'] for s in r['district_summary']],[1,1,1])
        self.assertEqual([s['target_count'] for s in r['district_summary']],[1,1,0])
        self.assertFalse(r['llm_called']);self.assertFalse(r['db_written'])
        self.assertIn('65.0000점',r['report_text'])

    def test_district_scope_does_not_leak_other_rows(self):
        self.data['scope']={'role':'district','district':'수정구'}
        r=build_report(self.data)
        self.assertEqual(len(r['district_summary']),1)
        for token in ['중원구','분당구','SYNTHETIC-GRID-2','SYNTHETIC-GRID-3']:
            self.assertNotIn(token,r['report_text'])
        self.assertEqual({x['gid'] for x in r['source_refs']},{'SYNTHETIC-GRID-1'})

    def test_unconfirmed_or_partial_snapshot_blocks(self):
        self.data['run_status']='draft'
        self.assertEqual(build_report(self.data)['error_codes'],['run_not_confirmed'])
        self.data['run_status']='confirmed';self.data['snapshot_complete']=False
        self.assertEqual(build_report(self.data)['error_codes'],['incomplete_snapshot'])

    def test_duplicate_grid_and_wrong_run(self):
        self.data['candidates'].append(deepcopy(self.data['candidates'][0]))
        self.assertEqual(build_report(self.data)['error_codes'],['duplicate_candidate'])
        self.data['candidates'].pop();self.data['run_id']='OTHER'
        self.assertEqual(build_report(self.data)['error_codes'],['mixed_run'])

    def test_missing_scores_not_treated_as_zero(self):
        card=self.data['candidates'][0]['request']['card'];card['score']=None;card['rank']=None
        r=build_report(self.data);s=r['district_summary'][0]
        self.assertEqual(s['missing_score_count'],1);self.assertEqual(s['known_score_count'],0)
        self.assertIsNone(s['score_min']);self.assertEqual(sum(s['score_distribution'].values()),0)
        self.assertIn('점수 모름',r['report_text'])

    def test_held_target_no_action_but_evidence_kept(self):
        r=build_report(self.data)
        self.assertIn('SYNTHETIC-GRID-3',r['sections'][1]['text'])
        self.assertNotIn('SYNTHETIC-GRID-3',r['sections'][4]['text'])

    def test_unreviewed_target_action_blocked(self):
        self.data['candidates'][0]['request']['action']['review_status']='draft'
        self.assertEqual(build_report(self.data)['error_codes'],['action_not_reviewed'])

    def test_law_confirmation_and_conflict(self):
        law={'reference_id':'L1','title':'가상 기준','article':'제1조','text':'가상 내용','review_status':'confirmed'}
        for row in self.data['candidates'][:2]:row['request']['laws']=[deepcopy(law)]
        r=build_report(self.data);self.assertEqual(r['sections'][2]['text'].count('가상 기준'),1)
        self.data['candidates'][1]['request']['laws'][0]['text']='다른 내용'
        self.assertEqual(build_report(self.data)['error_codes'],['conflicting_law_reference'])
        self.data['candidates'][0]['request']['laws'][0]['review_status']='draft'
        self.assertEqual(build_report(self.data)['error_codes'],['law_not_confirmed'])

    def test_empty_snapshot_not_unknown_population(self):
        self.data['candidates']=[];r=build_report(self.data)
        self.assertEqual(r['status'],'draft');self.assertEqual(sum(s['candidate_count'] for s in r['district_summary']),0)
        self.assertIn('전체 격자 수와는 다릅니다',r['report_text'])

    def test_contract_scope_and_year_validation(self):
        for field,value in [('data_kind','actual'),('report_year',True),('scope',{'role':'district','district':None})]:
            d=deepcopy(self.data);d[field]=value
            self.assertEqual(build_report(d)['status'],'blocked')
        self.data['candidates'][0]['request']['card']['calculation_year']=2025
        self.assertEqual(build_report(self.data)['error_codes'],['mixed_calculation_year'])

    def test_mixed_formula_version_blocked(self):
        self.data['candidates'][0]['request']['card']['formula_version']='OTHER'
        self.assertEqual(build_report(self.data)['error_codes'],['mixed_formula_versions'])

    def test_distribution_boundaries(self):
        self.data['candidates'][0]['request']['card']['score']='0.0000'
        self.data['candidates'][1]['request']['card']['score']='25.0000'
        self.data['candidates'][2]['request']['card']['score']='75.0000'
        r=build_report(self.data)
        self.assertEqual(r['district_summary'][0]['score_distribution']['0~25 미만'],1)
        self.assertEqual(r['district_summary'][1]['score_distribution']['25~50 미만'],1)
        self.assertEqual(r['district_summary'][2]['score_distribution']['75 이상'],1)

if __name__=='__main__':unittest.main()
