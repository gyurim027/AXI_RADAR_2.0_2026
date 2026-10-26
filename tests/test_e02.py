from copy import deepcopy
import json
from pathlib import Path
import unittest

from app.services.ai07.e02 import explain_card


class E02Tests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'samples' / 'cards.json'
        self.samples = json.loads(path.read_text(encoding='utf-8'))
        self.card = deepcopy(self.samples[0]['card'])

    def test_normal_result_preserves_score_rank_and_exact_facts(self):
        before = deepcopy(self.card)
        result = explain_card(self.card)
        self.assertEqual(result['status'], 'ok')
        self.assertIn('65.0000점', result['explanation'])
        self.assertIn('100개 격자 중 입력 순위 2위', result['explanation'])
        self.assertEqual(self.card, before)
        self.assertEqual(result['facts'], self.card)
        self.assertIsNot(result['facts'], self.card)

    def test_each_fact_keeps_its_own_year_source_unit_and_contribution(self):
        result = explain_card(self.card)
        text = result['explanation']
        self.assertIn('2025년 자료, 가상 항목 A: 2건, 제공된 점수 기여 20.0000점(출처: 가상 출처 A)', text)
        self.assertIn('2024년 자료, 가상 항목 B: 1곳, 제공된 점수 기여 15.0000점(출처: 가상 출처 B)', text)
        self.assertEqual(result['source_refs'][1]['basis_year'], 2024)

    def test_zero_is_preserved_without_safety_or_absence_judgment(self):
        text = explain_card(self.samples[1]['card'])['explanation']
        self.assertIn('점수 0.0000점', text)
        self.assertIn('가상 민원 기록: 0건', text)
        self.assertNotIn('안전', text)
        self.assertNotIn('문제없', text)

    def test_missing_and_unassessed_are_not_zero_and_are_separate(self):
        result = explain_card(self.samples[2]['card'])
        text = result['explanation']
        self.assertIn('점수 모름, 순위 모름', text)
        self.assertIn('모름(자료 없음', text)
        self.assertIn('모름(미평가', text)
        self.assertIn('자료 기준연도 미확인', text)
        self.assertIn('출처 미확인', text)
        self.assertNotIn('0점', text)

    def test_other_run_or_grid_is_blocked_without_explanation(self):
        for field in ['run_id', 'gid']:
            with self.subTest(field=field):
                card = deepcopy(self.card)
                card['evidence'][0][field] = 'SYNTHETIC-OTHER'
                result = explain_card(card)
                self.assertEqual(result['error_codes'], ['mixed_run_or_grid'])
                self.assertIsNone(result['explanation'])

    def test_rank_and_total_constraints(self):
        for field, value in [('rank', 101), ('rank', True), ('rank', 0), ('total', -1)]:
            with self.subTest(field=field, value=value):
                card = deepcopy(self.card)
                card[field] = value
                self.assertEqual(explain_card(card)['status'], 'blocked')

    def test_scope_is_required_when_rank_is_present(self):
        self.card['rank_scope'] = None
        self.assertEqual(explain_card(self.card)['error_codes'], ['rank_scope_required'])

    def test_no_total_does_not_invent_population(self):
        self.card['total'] = None
        text = explain_card(self.card)['explanation']
        self.assertIn('전체 대상 수 미제공', text)
        self.assertNotIn('100개', text)

    def test_nonfinite_numeric_types_and_negative_score_blocked(self):
        for value in ['NaN', 'Infinity', '-1', 65, True, '6e1', '1,000']:
            with self.subTest(value=value):
                self.card['score'] = value
                self.assertEqual(explain_card(self.card)['status'], 'blocked')

    def test_duplicate_evidence_and_unknown_fields_blocked(self):
        card = deepcopy(self.card)
        card['evidence'].append(deepcopy(card['evidence'][0]))
        self.assertEqual(explain_card(card)['error_codes'], ['duplicate_evidence_id'])
        self.card['make_up_reason'] = 'extra'
        self.assertEqual(explain_card(self.card)['status'], 'blocked')

    def test_observed_null_and_missing_with_values_are_conflicts(self):
        self.card['evidence'][0]['value'] = None
        self.assertEqual(explain_card(self.card)['error_codes'], ['observed_value_required'])
        card = deepcopy(self.samples[2]['card'])
        card['evidence'][0]['value'] = '0'
        self.assertEqual(explain_card(card)['error_codes'], ['missing_value_conflict'])

    def test_absent_contribution_is_not_calculated_or_summed(self):
        for item in self.card['evidence']:
            item['contribution_points'] = None
        result = explain_card(self.card)
        self.assertNotIn('제공된 점수 기여', result['explanation'])
        self.assertNotIn('때문', result['explanation'])
        self.assertIn('미제공 기여점수나 순위의 원인은 추정하지 않았습니다.', result['limitations'])

    def test_no_evidence_does_not_reuse_previous_candidate(self):
        self.card['evidence'] = []
        result = explain_card(self.card)
        self.assertIn('항목별 근거는 모름', result['explanation'])
        self.assertEqual(result['source_refs'], [])

    def test_judgment_or_control_characters_are_rejected(self):
        for text in ['안전하다', '우선 정비 필요', '가상\n추가 문장']:
            with self.subTest(text=text):
                card = deepcopy(self.card)
                card['evidence'][0]['label'] = text
                self.assertEqual(explain_card(card)['status'], 'blocked')

    def test_schema_is_synthetic_only_and_unknown_approval_is_not_approved(self):
        self.card['calculation_status'] = 'approval_unknown'
        text = explain_card(self.card)['explanation']
        self.assertIn('결과 승인 여부 미확인', text)
        self.assertNotIn('승인 전 시험 결과', text)
        self.card['data_kind'] = 'internal'
        self.assertEqual(explain_card(self.card)['status'], 'blocked')

    def test_result_is_repeatable_and_has_no_external_or_db_activity(self):
        a, b = explain_card(self.card), explain_card(self.card)
        self.assertEqual(a, b)
        self.assertEqual(len(a['sentences']), 2)
        self.assertFalse(a['external_api_called'])
        self.assertFalse(a['db_written'])


if __name__ == '__main__':
    unittest.main()
