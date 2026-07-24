import unittest

from price_algorithm import PROBAS, calculate_prices


class PriceAlgorithmTest(unittest.TestCase):
    def test_rate_1000_matches_the_approved_price_table(self):
        expected_from = {
            375: 645_000,
            583: 1_000_000,
            585: 1_000_000,
            750: 1_290_000,
            850: 1_460_000,
            875: 1_505_000,
            916: 1_575_000,
            999: 1_715_000,
        }
        expected_to = {
            "skupka": (715_000, 1_330_000, 1_180_000, 1_500_000, 1_530_000, 1_575_000, 1_645_000, 1_785_000),
            "diamant": (720_000, 1_335_000, 1_180_000, 1_500_000, 1_535_000, 1_580_000, 1_650_000, 1_790_000),
            "tillachi_bolla": (720_000, 1_335_000, 1_180_000, 1_500_000, 1_535_000, 1_580_000, 1_650_000, 1_790_000),
            "goldexpert": (725_000, 1_340_000, 1_180_000, 1_500_000, 1_540_000, 1_585_000, 1_655_000, 1_795_000),
        }

        all_prices = {brand: calculate_prices(1000, brand) for brand in expected_to}

        for proba in PROBAS:
            self.assertEqual(expected_from[proba], all_prices["diamant"][proba]["from"])

        for brand, to_prices in expected_to.items():
            for proba, to_price in zip(PROBAS, to_prices):
                self.assertEqual(to_price, all_prices[brand][proba]["to"])

        self.assertEqual(all_prices["diamant"], all_prices["tillachi_bolla"])


if __name__ == "__main__":
    unittest.main()
