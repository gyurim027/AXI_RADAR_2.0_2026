from copy import deepcopy
import json
from pathlib import Path
import unittest
from app.services.ai07.e02 import explain_card
from app.services.ai07.e03 import refine_card, suggest_local

class E03Tests(unittest.TestCase):
    def setUp(self):
        self.cards = json.loads((Path(__file__).resolve().parents[1]/'samples/cards.json').read_text(encoding='utf-8'))
        self.card = deepcopy(self.cards[0]['card'])
        self.original = explain_card(self.card)['explanation']

    def test_permitted_rewrite(self):
        result = refine_card(self.card)
        self.assertTrue(result['accepted'])
        self.assertIn('제공된 값은', result['explanation'])
        self.assertFalse(result['llm_called'])

    def test_changed_score_falls_back(self):
        result = refine_card(self.card, self.original.replace('65.0000점','66.0000점'))
        self.assertEqual(result['refinement_status'],'fallback')
        self.assertEqual(result['explanation'],self.original)

    def test_same_numbers_different_relationship_rejected(self):
        text = self.original.replace('점수 65.0000점','점수 2점').replace('입력 순위 2위','입력 순위 65.0000위')
        self.assertFalse(refine_card(self.card,text)['accepted'])

    def test_year_source_reason_and_identity_changes_rejected(self):
        for before, after in [('2025년','2026년'),('가상 출처 A','다른 출처'),
                              (self.card['gid'],'OTHER-GRID'),('가상 항목 A','가상 항목 B')]:
            with self.subTest(before=before):
                changed=self.original.replace(before,after)
                self.assertNotEqual(changed,self.original)
                self.assertFalse(refine_card(self.card,changed)['accepted'])

    def test_added_claim_and_judgments_rejected(self):
        for claim in ['안전합니다.','위험한 지역입니다.','시급한 조치가 필요합니다.','보도가 좁아서 이 순위입니다.']:
            with self.subTest(claim=claim):
                self.assertFalse(refine_card(self.card,self.original+' '+claim)['accepted'])

    def test_missing_not_zero(self):
        card=self.cards[2]['card'];original=explain_card(card)['explanation']
        self.assertFalse(refine_card(card,original.replace('점수 모름','점수 0점'))['accepted'])
        self.assertIn('모름',refine_card(card)['explanation'])

    def test_empty_invalid_and_omission(self):
        for proposal in ['', {}, self.original.split('. ')[0]]:
            with self.subTest(proposal=proposal):
                self.assertEqual(refine_card(self.card,proposal)['refinement_status'],'fallback')

    def test_input_unchanged_and_invalid_card_blocked(self):
        original=deepcopy(self.card);refine_card(self.card)
        self.assertEqual(original,self.card)
        self.card['evidence'][0]['run_id']='OTHER'
        self.assertEqual(refine_card(self.card)['refinement_status'],'blocked')

if __name__=='__main__':unittest.main()
