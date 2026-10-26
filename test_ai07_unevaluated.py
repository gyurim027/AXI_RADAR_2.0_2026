import unittest
from run_ai07_unevaluated import explain

def sample(state="NOT_SURVEYED", value=None):
    return {
        "official_use": False,
        "run_id": "SYNTHETIC-RUN",
        "gid": "SYNTHETIC-GRID",
        "score": None,
        "rank_no": None,
        "domain_scores": None,
        "indicator_contributions": None,
        "observation": {
            "indicator": "COND_적치물_수",
            "state": state,
            "value": value,
        },
    }

class ExplanationTests(unittest.TestCase):
    def test_not_surveyed(self):
        text = explain(sample())
        self.assertIn("미조사", text)
        self.assertNotIn("관측 건수는 0건", text)

    def test_observed_seven(self):
        text = explain(sample("OBSERVED_VALUE", "7.0"))
        self.assertIn("관측 건수는 7건", text)

    def test_observed_zero(self):
        text = explain(sample("OBSERVED_ZERO", "0.0"))
        self.assertIn("관측 건수는 0건", text)
        self.assertIn("안전 여부를 판단하지 않습니다", text)

    def test_missing_scores_not_invented(self):
        text = explain(sample())
        self.assertIn("점수와 순위가 제공되지 않아", text)
        self.assertIn("기여점도 제공되지 않았습니다", text)
        self.assertNotIn("0점", text)
        self.assertNotIn("1위", text)

    def test_official_input_blocked(self):
        item = sample()
        item["official_use"] = True
        with self.assertRaises(ValueError):
            explain(item)

    def test_present_or_missing_score_fields_blocked(self):
        for key in ("score", "rank_no", "domain_scores", "indicator_contributions"):
            with self.subTest(field=key, problem="value_present"):
                item = sample()
                item[key] = 99
                with self.assertRaises(ValueError):
                    explain(item)
            with self.subTest(field=key, problem="field_missing"):
                item = sample()
                del item[key]
                with self.assertRaises(ValueError):
                    explain(item)

    def test_contradictory_states_blocked(self):
        cases = [
            ("NOT_SURVEYED", "0"),
            ("OBSERVED_ZERO", "7"),
            ("OBSERVED_VALUE", "0"),
            ("UNKNOWN", None),
        ]
        for state, value in cases:
            with self.subTest(state=state, value=value):
                with self.assertRaises(ValueError):
                    explain(sample(state, value))

    def test_invalid_counts_blocked(self):
        for value in ("-1", "1.5", "NaN", "Infinity", None, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    explain(sample("OBSERVED_VALUE", value))

if __name__ == "__main__":
    unittest.main()
