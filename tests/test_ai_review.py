import unittest

from src.desk.ai_review import build_review_input, unavailable_review, validate_review


class FakeOpportunity:
    state = "WATCH"
    setup_type = "test"
    score = 70
    data_quality = "A"
    btc_context = "neutral"
    news_risk = "N/A"
    diagnostics = {}


class AIReviewTests(unittest.TestCase):
    def test_unavailable_review_is_safe(self):
        review = unavailable_review()
        self.assertEqual(review["status"], "N/A")
        self.assertEqual(review["shadow_recommendation"], "NO_TRADE_UNTIL_AI_REVIEW_AVAILABLE")

    def test_review_input_is_structured(self):
        data = build_review_input("BTCUSDT", FakeOpportunity(), None, {"status": "N/A"}, {"overall": "neutral"})
        self.assertEqual(data["mode"], "shadow_only")
        self.assertEqual(data["symbol"], "BTCUSDT")

    def test_review_validation_limits_shape(self):
        result = validate_review({"context_summary": "ok", "confidence": 0.7, "extra": "discard"})
        self.assertNotIn("extra", result)
        self.assertEqual(result["confidence"], 0.7)


if __name__ == "__main__":
    unittest.main()
