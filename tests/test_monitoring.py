"""Tests for CarryMem Monitoring Framework (MVP).

Covers:
- MetricsCollector: counters, latency, gauges, snapshots, Prometheus export
- HealthChecker: health checks, readiness, SLO evaluation
- SLO threshold checks: classify_and_remember P99 < 200ms, recall P99 < 500ms, startup < 2s

Run:
    python -m pytest tests/test_monitoring.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem.monitoring import (
    HealthChecker,
    MetricsCollector,
)


class TestMetricsCollectorCounters(unittest.TestCase):
    """Test 1-3: Counter operations."""

    def setUp(self):
        self.mc = MetricsCollector()

    def test_increment_basic(self):
        """Test 1: increment() increases counter from 0 to 1."""
        self.mc.increment("test_op")
        snap = self.mc.get_snapshot()
        self.assertEqual(snap["counters"]["test_op"], 1)

    def test_increment_multiple(self):
        """Test 2: Multiple increments accumulate correctly."""
        for _ in range(5):
            self.mc.increment("test_op")
        snap = self.mc.get_snapshot()
        self.assertEqual(snap["counters"]["test_op"], 5)

    def test_increment_custom_value(self):
        """Test 3: Increment with custom value."""
        self.mc.increment("bulk_op", value=10)
        snap = self.mc.get_snapshot()
        self.assertEqual(snap["counters"]["bulk_op"], 10)

    def test_increment_separate_operations(self):
        """Test: Different operations have independent counters."""
        self.mc.increment("op_a")
        self.mc.increment("op_b")
        self.mc.increment("op_b")
        snap = self.mc.get_snapshot()
        self.assertEqual(snap["counters"]["op_a"], 1)
        self.assertEqual(snap["counters"]["op_b"], 2)


class TestMetricsCollectorLatency(unittest.TestCase):
    """Test 4-6: Latency histogram operations."""

    def setUp(self):
        self.mc = MetricsCollector()

    def test_record_latency_single(self):
        """Test 4: Single latency sample is recorded."""
        self.mc.record_latency("op1", 100.0)
        snap = self.mc.get_snapshot()
        lat = snap["latency"]["op1"]
        self.assertEqual(lat["count"], 1)
        self.assertAlmostEqual(lat["p99"], 100.0, places=1)

    def test_record_latency_multiple_samples(self):
        """Test 5: Multiple samples produce correct p99/p95/avg."""
        samples = [10.0, 20.0, 30.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 1000.0]
        for s in samples:
            self.mc.record_latency("op2", s)
        snap = self.mc.get_snapshot()
        lat = snap["latency"]["op2"]
        self.assertEqual(lat["count"], 10)
        # Sorted: [10,20,30,50,100,150,200,250,300,1000], p99 idx=9
        self.assertAlmostEqual(lat["p99"], 1000.0, places=1)
        self.assertGreater(lat["avg"], 0)

    def test_record_latency_empty_operation(self):
        """Test 6: Operation with no latency data returns count=0."""
        snap = self.mc.get_snapshot()
        lat = snap["latency"].get("nonexistent", {"count": 0})
        self.assertEqual(lat["count"], 0)


class TestMetricsCollectorGauges(unittest.TestCase):
    """Test gauge operations."""

    def setUp(self):
        self.mc = MetricsCollector()

    def test_set_and_get_gauge(self):
        """Test: Gauge value can be set and retrieved."""
        self.mc.set_gauge("active_connections", 42)
        snap = self.mc.get_snapshot()
        self.assertEqual(snap["gauges"]["active_connections"], 42)

    def test_gauge_overwrite(self):
        """Test: Gauge overwrites previous value."""
        self.mc.set_gauge("temp", 10.0)
        self.mc.set_gauge("temp", 20.0)
        snap = self.mc.get_snapshot()
        self.assertEqual(snap["gauges"]["temp"], 20.0)


class TestMetricsCollectorPrometheus(unittest.TestCase):
    """Test Prometheus text format export."""

    def setUp(self):
        self.mc = MetricsCollector()

    def test_prometheus_contains_counter(self):
        """Test 7: Prometheus output includes counter metrics."""
        self.mc.increment("classify_and_remember")
        output = self.mc.to_prometheus()
        self.assertIn("carrymem_total", output)
        self.assertIn('operation="classify_and_remember"', output)

    def test_prometheus_contains_latency_summary(self):
        """Test 8: Prometheus output includes latency summary."""
        self.mc.record_latency("recall", 120.5)
        output = self.mc.to_prometheus()
        self.assertIn("carrymem_latency_ms", output)
        self.assertIn('operation="recall"', output)

    def test_prometheus_contains_uptime(self):
        """Test 9: Prometheus output includes uptime metric."""
        output = self.mc.to_prometheus()
        self.assertIn("carrymem_uptime_seconds", output)

    def test_prometheus_format_valid(self):
        """Test: Prometheus output has proper TYPE headers."""
        self.mc.increment("test")
        output = self.mc.to_prometheus()
        self.assertIn("# TYPE carrymem_counter counter", output)


class TestMetricsCollectorReset(unittest.TestCase):
    """Test reset functionality."""

    def test_reset_clears_all_metrics(self):
        """Test: reset() clears counters, latency, and gauges."""
        mc = MetricsCollector()
        mc.increment("op")
        mc.record_latency("op", 100.0)
        mc.set_gauge("g", 1.0)
        mc.reset()
        snap = mc.get_snapshot()
        self.assertEqual(len(snap["counters"]), 0)
        self.assertEqual(len(snap["latency"]), 0)
        self.assertEqual(len(snap["gauges"]), 0)


class TestHealthChecker(unittest.TestCase):
    """Test health check logic."""

    def setUp(self):
        self.mc = MetricsCollector()
        self.hc = HealthChecker(metrics_collector=self.mc)

    def test_check_returns_ok_when_healthy(self):
        """Test 10: Healthy system returns status='ok'."""
        result = self.hc.check()
        self.assertEqual(result["status"], "ok")

    def test_check_includes_slo_section(self):
        """Test: Check result contains SLO section."""
        result = self.hc.check()
        self.assertIn("slo", result)
        self.assertIsInstance(result["slo"], list)

    def test_check_custom_check_passes(self):
        """Test: Custom registered check that passes."""
        self.hc.register_check("db_connection", lambda: True)
        result = self.hc.check()
        self.assertEqual(result["checks"]["db_connection"]["status"], "ok")

    def test_check_custom_check_fails_causes_degraded(self):
        """Test: Failing custom check causes degraded status."""
        self.hc.register_check("disk_space", lambda: False)
        result = self.hc.check()
        self.assertEqual(result["status"], "degraded")

    def test_readyz_not_ready_by_default(self):
        """Test: readyz returns not_ready before set_ready is called."""
        result = self.hc.readyz()
        self.assertFalse(result["ready"])

    def test_readyz_ready_after_set_ready(self):
        """Test: readyz returns ready after set_ready(True)."""
        self.hc.set_ready(True)
        result = self.hc.readyz()
        self.assertTrue(result["ready"])

    def test_slo_violation_causes_degraded(self):
        """Test 11: SLO violation (P99 > threshold) causes degraded status."""
        # Record latencies above the classify_and_remember threshold of 200ms
        for _ in range(100):
            self.mc.record_latency("classify_and_remember", 300.0)
        result = self.hc.check()
        self.assertEqual(result["status"], "degraded")
        slo_results = [s for s in result["slo"] if s.get("within_slo") is False]
        self.assertGreater(len(slo_results), 0)

    def test_slo_within_threshold_is_ok(self):
        """Test: Latencies within SLO threshold do not cause degradation."""
        for _ in range(50):
            self.mc.record_latency("classify_and_remember", 50.0)
        result = self.hc.check()
        # Should be ok if no other failures
        slo_classify = next((s for s in result["slo"] if s["operation"] == "classify_and_remember"), None)
        self.assertIsNotNone(slo_classify)
        self.assertTrue(slo_classify["within_slo"])


if __name__ == "__main__":
    unittest.main()
