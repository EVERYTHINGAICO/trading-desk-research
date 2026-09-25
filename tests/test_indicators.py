import unittest

from src.desk.indicators import bollinger, ema, kdj, macd, psar, rsi, supertrend
from src.desk.types import Candle


class IndicatorTests(unittest.TestCase):
    def test_ema_requires_history(self):
        self.assertIsNone(ema([1, 2], 3))
        self.assertAlmostEqual(ema(list(range(1, 11)), 3), 9.0, places=6)

    def test_bollinger_shape(self):
        result = bollinger(list(range(1, 22)))
        self.assertIsNotNone(result)
        self.assertLess(result["lower"], result["middle"])
        self.assertLess(result["middle"], result["upper"])

    def test_rsi_direction(self):
        self.assertEqual(rsi(list(range(1, 20)), 6), 100.0)
        self.assertEqual(rsi(list(range(20, 1, -1)), 6), 0.0)

    def test_macd_returns_structured_values(self):
        result = macd(list(range(1, 80)))
        self.assertIn("dif", result)
        self.assertIn("dea", result)
        self.assertIn("histogram", result)

    def test_quality_stock_indicators_return_values(self):
        candles = [Candle(i, i + 1, i + 2, i, i + 1.5, 100, 1000) for i in range(120)]
        self.assertIsNotNone(kdj(candles)["k"])
        self.assertIsNotNone(psar(candles)["value"])
        self.assertIsNotNone(supertrend(candles)["value"])


if __name__ == "__main__":
    unittest.main()
