"""Unit tests for _percentile and _latency_buckets helpers (TASK-344, PE-001 to PE-005)."""
from __future__ import annotations

import unittest

from solo_builder.api.blueprints.metrics import _percentile, _latency_buckets


class TestPercentile(unittest.TestCase):

    def test_empty_list_returns_zero(self):
        self.assertEqual(_percentile([], 0.5), 0.0)

    def test_single_element(self):
        self.assertEqual(_percentile([5.0], 0.5), 5.0)

    def test_median_of_ten(self):
        values = sorted(float(i) for i in range(1, 11))
        result = _percentile(values, 0.50)
        # With n=10, idx = max(0, int(10*0.5)-1) = 4 → values[4] = 5.0
        self.assertEqual(result, 5.0)

    def test_p95_of_twenty(self):
        values = sorted(float(i) for i in range(1, 21))
        result = _percentile(values, 0.95)
        # idx = max(0, int(20*0.95)-1) = 18 → values[18] = 19.0
        self.assertEqual(result, 19.0)

    def test_p99_gte_p95(self):
        values = sorted(float(i) for i in range(1, 101))
        self.assertGreaterEqual(_percentile(values, 0.99), _percentile(values, 0.95))

    def test_p95_gte_p50(self):
        values = sorted(float(i) for i in range(1, 101))
        self.assertGreaterEqual(_percentile(values, 0.95), _percentile(values, 0.50))

    def test_result_rounded_to_4dp(self):
        values = [1.123456789]
        result = _percentile(values, 0.5)
        # Should be rounded to 4 decimal places
        self.assertEqual(result, round(1.123456789, 4))


class TestLatencyBuckets(unittest.TestCase):

    def test_empty_list(self):
        buckets = _latency_buckets([])
        self.assertEqual(sum(buckets.values()), 0)

    def test_five_keys_always_present(self):
        buckets = _latency_buckets([])
        for key in ("lt_1s", "1s_5s", "5s_10s", "10s_30s", "gt_30s"):
            self.assertIn(key, buckets)

    def test_lt_1s_boundary(self):
        # 0.0 and 0.999 → lt_1s; 1.0 → 1s_5s
        buckets = _latency_buckets([0.0, 0.999, 1.0])
        self.assertEqual(buckets["lt_1s"], 2)
        self.assertEqual(buckets["1s_5s"], 1)

    def test_1s_5s_boundary(self):
        # 1.0, 4.999 → 1s_5s; 5.0 → 5s_10s
        buckets = _latency_buckets([1.0, 4.999, 5.0])
        self.assertEqual(buckets["1s_5s"], 2)
        self.assertEqual(buckets["5s_10s"], 1)

    def test_5s_10s_boundary(self):
        # 5.0, 9.999 → 5s_10s; 10.0 → 10s_30s
        buckets = _latency_buckets([5.0, 9.999, 10.0])
        self.assertEqual(buckets["5s_10s"], 2)
        self.assertEqual(buckets["10s_30s"], 1)

    def test_10s_30s_boundary(self):
        # 10.0, 29.999 → 10s_30s; 30.0 → gt_30s
        buckets = _latency_buckets([10.0, 29.999, 30.0])
        self.assertEqual(buckets["10s_30s"], 2)
        self.assertEqual(buckets["gt_30s"], 1)

    def test_gt_30s(self):
        buckets = _latency_buckets([30.0, 100.0, 999.9])
        self.assertEqual(buckets["gt_30s"], 3)

    def test_sum_equals_input_length(self):
        values = [0.5, 2.0, 7.0, 20.0, 45.0, 1.0, 9.9]
        buckets = _latency_buckets(values)
        self.assertEqual(sum(buckets.values()), len(values))

    def test_all_lt_1s(self):
        values = [0.1, 0.2, 0.3]
        buckets = _latency_buckets(values)
        self.assertEqual(buckets["lt_1s"], 3)
        self.assertEqual(buckets["1s_5s"], 0)

    def test_all_gt_30s(self):
        values = [31.0, 60.0, 120.0]
        buckets = _latency_buckets(values)
        self.assertEqual(buckets["gt_30s"], 3)
        self.assertEqual(buckets["lt_1s"], 0)


if __name__ == "__main__":
    unittest.main()
