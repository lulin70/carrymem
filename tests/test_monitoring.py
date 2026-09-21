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
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem import monitoring
from carrymem.carrymem import CarryMem
from carrymem.exceptions import ValidationError
from carrymem.monitoring import (
    HealthChecker,
    MetricsCollector,
    get_metrics_collector,
    record_startup_once,
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
        self.assertIs(result["ready"], True)

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
        self.assertIs(slo_classify["within_slo"], True)


class TestProcessCollector(unittest.TestCase):
    """The exporter and the instrumentation writers must share one instance."""

    def test_get_metrics_collector_is_process_wide_singleton(self):
        """Repeated calls return the same collector — otherwise /metrics can
        never observe samples written by core operation paths."""
        self.assertIs(get_metrics_collector(), get_metrics_collector())
        self.assertIs(get_metrics_collector(), get_metrics_collector())

    def test_written_sample_is_visible_to_a_second_caller(self):
        """A sample written through one reference is readable through another."""
        get_metrics_collector().reset()
        get_metrics_collector().increment("shared_probe")
        self.assertEqual(get_metrics_collector().get_snapshot()["counters"]["shared_probe"], 1)
        get_metrics_collector().reset()


class TestStartupInstrumentation(unittest.TestCase):
    """`startup` is a one-shot, process-level measurement."""

    def setUp(self):
        self.mc = get_metrics_collector()
        self.mc.reset()
        self._saved = (monitoring._STARTUP_REFERENCE, monitoring._STARTUP_RECORDED)

    def tearDown(self):
        monitoring._STARTUP_REFERENCE, monitoring._STARTUP_RECORDED = self._saved
        self.mc.reset()

    def test_records_latency_measured_from_the_package_import_reference(self):
        """The sample covers the window opened at package import."""
        monitoring._STARTUP_REFERENCE = time.perf_counter() - 0.05
        monitoring._STARTUP_RECORDED = False

        record_startup_once()

        stats = self.mc.get_snapshot()["latency"]["startup"]
        self.assertEqual(stats["count"], 1)
        self.assertGreaterEqual(stats["p99"], 40.0, "should measure the ~50ms reference window")

    def test_second_call_does_not_add_another_sample(self):
        """A second construction must not record process uptime as 'startup'."""
        monitoring._STARTUP_REFERENCE = time.perf_counter() - 0.05
        monitoring._STARTUP_RECORDED = False

        record_startup_once()
        record_startup_once()

        self.assertEqual(self.mc.get_snapshot()["latency"]["startup"]["count"], 1)

    def test_no_sample_without_a_reference(self):
        """Without the import reference there is nothing meaningful to record."""
        monitoring._STARTUP_REFERENCE = None
        monitoring._STARTUP_RECORDED = False

        record_startup_once()

        self.assertNotIn("startup", self.mc.get_snapshot()["latency"])


class TestCoreOperationInstrumentation(unittest.TestCase):
    """The /metrics series must be produced by real core operation paths."""

    def setUp(self):
        self.mc = get_metrics_collector()
        self.mc.reset()
        self.cm = CarryMem(storage="sqlite", db_path=":memory:")

    def tearDown(self):
        self.cm.close()
        self.mc.reset()

    def test_control_group_publishes_nothing_before_an_operation_runs(self):
        """Control group: absence of series proves later assertions are not vacuous."""
        snap = self.mc.get_snapshot()
        self.assertEqual(snap["counters"], {})
        self.assertNotIn("classify_and_remember", snap["latency"])
        self.assertNotIn("recall", snap["latency"])

    def test_classify_and_remember_records_counter_and_latency(self):
        result = self.cm.classify_and_remember("I prefer dark mode for coding")
        self.assertTrue(result["stored"], f"expected a stored memory, got {result}")

        snap = self.mc.get_snapshot()
        self.assertEqual(snap["counters"]["classify_and_remember"], 1)
        self.assertEqual(snap["latency"]["classify_and_remember"]["count"], 1)

    def test_recall_memories_records_counter_and_latency(self):
        self.cm.classify_and_remember("I prefer dark mode for coding")
        before = self.mc.get_snapshot()["counters"].get("recall", 0)

        hits = self.cm.recall_memories("dark mode")
        self.assertGreaterEqual(len(hits), 1)

        snap = self.mc.get_snapshot()
        self.assertGreater(snap["counters"]["recall"], before)
        self.assertGreaterEqual(snap["latency"]["recall"]["count"], 1)

    def test_failed_classify_records_error_counter_and_reraises(self):
        """A failing operation must be visible: silence would look like health."""
        with self.assertRaises(ValidationError):
            self.cm.classify_and_remember("")

        snap = self.mc.get_snapshot()
        self.assertEqual(snap["counters"].get("classify_and_remember", 0), 0)
        self.assertEqual(snap["counters"]["classify_and_remember_errors"], 1)
        self.assertEqual(snap["latency"]["classify_and_remember"]["count"], 1)

    def test_storing_a_memory_does_not_count_as_a_recall(self):
        """Storing reads memories internally; those reads are not user recalls.

        ``classify_and_remember`` reads existing memories as a side effect of
        storing, through three independent paths: the rule candidate generator,
        coreference resolution (only when the message contains a pronoun), and
        correction-history analysis. Each one went through the instrumented
        ``recall_memories``, inflating ``carrymem_total{operation="recall"}``
        (measured: +2 from the rule path, +1 more from coreference) and diluting
        the recall latency SLO with fast internal lookups.

        Every message shape is exercised on purpose: an earlier version of this
        guard used only a pronoun-free message, so the coreference leak survived
        the fix unnoticed.
        """
        messages = [
            "I prefer dark mode for coding",  # rule path only
            "I prefer dark mode in all my editors",  # + coreference ("my")
            "We decided to ship it next week",  # + coreference ("it")
            "Actually, I prefer light mode instead of dark mode",  # + correction path
        ]

        for message in messages:
            with self.subTest(message=message):
                self.mc.reset()
                self.cm.classify_and_remember(message)

                snapshot = self.mc.get_snapshot()
                self.assertEqual(snapshot["counters"]["classify_and_remember"], 1)
                self.assertNotIn(
                    "recall",
                    snapshot["counters"],
                    f"internal reads during storing leaked into the recall counter for {message!r}",
                )
                self.assertNotIn("recall", snapshot["latency"])

    def test_an_explicit_recall_still_counts(self):
        """Control group: the guard above must not be satisfied by never counting."""
        self.cm.classify_and_remember("I prefer dark mode for coding")
        self.mc.reset()

        self.cm.recall_memories("dark mode")

        snapshot = self.mc.get_snapshot()
        self.assertEqual(snapshot["counters"]["recall"], 1)
        self.assertEqual(snapshot["latency"]["recall"]["count"], 1)

    def test_slo_entries_report_real_values_not_no_data(self):
        """HealthChecker must consume the same collector the core writes to.

        This asserts the *wiring*, not the latency: the operation entries must
        carry real samples instead of the `no_data` placeholder. It deliberately
        does not assert `within_slo is True` — that would measure the host, not
        the code. The first operation on a fresh adapter pays one-time
        initialisation (schema, FTS triggers, language detection) and coverage
        instrumentation alone inflates it ~14x (7.5ms -> 106ms locally), so on a
        slower CI runner a cold first call legitimately exceeds the steady-state
        target. Whether the threshold can actually fail is covered by
        `test_slo_flags_a_breach_when_p99_exceeds_the_target`.
        """
        self.cm.classify_and_remember("I prefer dark mode for coding")
        self.cm.recall_memories("dark mode")

        slo = {entry["operation"]: entry for entry in HealthChecker(metrics_collector=self.mc).check()["slo"]}
        self.assertNotEqual(slo["classify_and_remember"].get("status"), "no_data")
        self.assertNotEqual(slo["recall"].get("status"), "no_data")

        # One sample each proves HealthChecker reads the collector the core wrote
        # into, rather than a second, empty instance.
        snapshot = self.mc.get_snapshot()
        self.assertEqual(snapshot["latency"]["classify_and_remember"]["count"], 1)
        self.assertEqual(snapshot["latency"]["recall"]["count"], 1)
        self.assertIsInstance(slo["classify_and_remember"]["within_slo"], bool)
        self.assertIsInstance(slo["recall"]["within_slo"], bool)

    def test_slo_reports_no_data_before_the_operation_runs(self):
        """Control group: `not no_data` above is only meaningful if `no_data` exists."""
        slo = {entry["operation"]: entry for entry in HealthChecker(metrics_collector=self.mc).check()["slo"]}

        self.assertEqual(slo["classify_and_remember"]["status"], "no_data")
        self.assertEqual(slo["recall"]["status"], "no_data")

    def test_slo_flags_a_breach_when_p99_exceeds_the_target(self):
        """The SLO must be able to fail; a threshold that never trips is decoration.

        Machine-independent on purpose: the sample is injected, so this holds on
        any host regardless of how fast it runs the real operation.
        """
        self.mc.record_latency("classify_and_remember", 5000.0)

        report = HealthChecker(metrics_collector=self.mc).check()
        slo = {entry["operation"]: entry for entry in report["slo"]}

        self.assertIs(slo["classify_and_remember"]["within_slo"], False)
        self.assertEqual(slo["classify_and_remember"]["threshold_ms"], 200.0)
        self.assertEqual(report["status"], "degraded")


class TestPrometheusExpositionContract(unittest.TestCase):
    """`/metrics` is an external contract: every emitted line must be parseable."""

    def test_each_gauge_declares_its_own_type(self):
        mc = MetricsCollector()
        mc.set_gauge("carrymem_sse_clients", 3)
        output = mc.to_prometheus()
        self.assertIn("# TYPE carrymem_sse_clients gauge", output)
        self.assertIn("carrymem_sse_clients 3", output)

    def test_no_unparseable_none_values_below_20_samples(self):
        """p95 is undefined for <=20 samples; it must be omitted, not printed as None."""
        mc = MetricsCollector()
        mc.record_latency("few_samples", 12.5)
        output = mc.to_prometheus()
        self.assertNotIn("None", output)
        self.assertIn('quantile="0.99"', output)

    def test_half_quantile_reports_the_median_not_the_mean(self):
        """quantile="0.5" must be a real median (avg would misrepresent the tail)."""
        mc = MetricsCollector()
        for value in (1.0, 2.0, 100.0):
            mc.record_latency("skewed", value)
        output = mc.to_prometheus()
        self.assertIn('carrymem_latency_ms{operation="skewed",quantile="0.5"} 2.0', output)


if __name__ == "__main__":
    unittest.main()
