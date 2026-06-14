"""Tests for CarryMem Monitoring & Alerting Framework (MVP).

Covers:
- MetricsCollector: counters, latency, gauges, snapshots, Prometheus export
- HealthChecker: health checks, readiness, SLO evaluation
- AlertManager: alert generation, formatting, SLO violation detection
- MonitoringHTTPServer: endpoint routing (via mock)
- LatencyTimer: context manager
- SLO threshold checks: classify_and_remember P99 < 200ms, recall P99 < 500ms, startup < 2s

Run:
    python -m pytest tests/test_monitoring.py -v
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem.monitoring import (
    Alert,
    AlertManager,
    AlertSeverity,
    HealthChecker,
    LatencyTimer,
    MetricsCollector,
    MonitoringHTTPServer,
    SLOTarget,
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


class TestAlertManager(unittest.TestCase):
    """Test alert generation and formatting."""

    def setUp(self):
        self.am = AlertManager()

    def test_no_alerts_when_within_slo(self):
        """Test: No alerts when all metrics are within SLO."""
        mc = MetricsCollector()
        for _ in range(50):
            mc.record_latency("classify_and_remember", 50.0)
            mc.record_latency("recall", 100.0)
        snapshot = mc.get_snapshot()
        alerts = self.am.check_alerts(snapshot)
        self.assertEqual(len(alerts), 0)

    def test_alert_on_slo_violation(self):
        """Test 12: Alert generated when P99 exceeds SLO threshold."""
        mc = MetricsCollector()
        # Record enough high-latency samples to push p99 above 200ms
        for _ in range(100):
            mc.record_latency("classify_and_remember", 350.0)
        snapshot = mc.get_snapshot()
        alerts = self.am.check_alerts(snapshot)
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0].severity, AlertSeverity.WARNING)

    def test_alert_format_contains_key_info(self):
        """Test: Formatted alert string contains key information."""
        alert = Alert(
            severity=AlertSeverity.WARNING,
            metric_name="test_p99",
            message="SLO violation detected",
            threshold=200.0,
            actual_value=350.0,
        )
        formatted = AlertManager.format_alert(alert)
        self.assertIn("WARNING", formatted)
        self.assertIn("test_p99", formatted)
        self.assertIn("350.0", formatted)

    def test_alert_history_tracking(self):
        """Test: Alerts are tracked in history."""
        mc = MetricsCollector()
        for _ in range(100):
            mc.record_latency("startup", 3000.0)  # exceeds 2s threshold
        snapshot = mc.get_snapshot()
        self.am.check_alerts(snapshot)
        history = self.am.get_alert_history()
        self.assertGreater(len(history), 0)

    def test_clear_history(self):
        """Test: Alert history can be cleared."""
        mc = MetricsCollector()
        for _ in range(100):
            mc.record_latency("classify_and_remember", 300.0)
        snapshot = mc.get_snapshot()
        self.am.check_alerts(snapshot)
        self.am.clear_history()
        self.assertEqual(len(self.am.get_alert_history()), 0)

    def test_recall_slo_violation_alert(self):
        """Test: recall P99 > 500ms triggers warning."""
        mc = MetricsCollector()
        for _ in range(100):
            mc.record_latency("recall", 600.0)
        snapshot = mc.get_snapshot()
        alerts = self.am.check_alerts(snapshot)
        self.assertGreater(len(alerts), 0)
        self.assertTrue(any("recall" in a.metric_name for a in alerts))


class TestLatencyTimer(unittest.TestCase):
    """Test the LatencyTimer context manager."""

    def test_timer_records_latency(self):
        """Test: LatencyTimer records elapsed time as latency."""
        mc = MetricsCollector()
        with LatencyTimer(mc, "timed_op"):
            time.sleep(0.05)  # ~50ms
        snap = mc.get_snapshot()
        lat = snap["latency"]["timed_op"]
        self.assertEqual(lat["count"], 1)
        self.assertGreater(lat["p99"], 40)  # at least 40ms
        self.assertLess(lat["p99"], 200)  # but not absurdly high


class TestMonitoringHTTPServerEndpoints(unittest.TestCase):
    """Test monitoring HTTP server endpoint routing via async runner."""

    def _run_server_test(self, path: str, expected_status: int = 200, check_body: callable = None):
        """Helper: start server, make a raw request, verify response."""
        mc = MetricsCollector()
        hc = HealthChecker(metrics_collector=mc)
        am = AlertManager()
        server = MonitoringHTTPServer(
            host="127.0.0.1",
            port=0,  # OS picks free port
            health_checker=hc,
            metrics_collector=mc,
            alert_manager=am,
        )

        async def run_test():
            await server.start_nonblocking()
            # Get actual port
            actual_port = server._server.sockets[0].getsockname()[1]

            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", actual_port)
                writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
                await writer.drain()

                response = await reader.readuntil(b"\r\n\r\n")
                header_str = response.decode("utf-8", errors="replace").split("\r\n")[0]
                # e.g. "HTTP/1.1 200 OK"
                status_code = int(header_str.split(" ")[1])
                self.assertEqual(status_code, expected_status, f"Expected {expected_status}, got {header_str}")

                if check_body:
                    body_bytes = await reader.read(4096)
                    check_body(body_bytes)
            finally:
                await server.stop()

        asyncio.run(run_test())

    def test_healthz_endpoint(self):
        """Test: GET /healthz returns 200 JSON with status field."""

        def check(body_bytes):
            data = json.loads(body_bytes.decode())
            self.assertIn(data["status"], ("ok", "degraded"))

        self._run_server_test("/healthz", 200, check_body=check)

    def test_metrics_endpoint(self):
        """Test: GET /metrics returns 200 with Prometheus format."""

        def check(body_bytes):
            text = body_bytes.decode()
            self.assertIn("# TYPE", text)

        self._run_server_test("/metrics", 200, check_body=check)

    def test_readyz_not_ready_returns_503(self):
        """Test: GET /readyz returns 503 when not ready."""
        self._run_server_test("/readyz", 503)

    def test_readyz_ready_returns_200(self):
        """Test: GET /readyz returns 200 when ready."""
        mc = MetricsCollector()
        hc = HealthChecker(metrics_collector=mc)
        hc.set_ready(True)
        am = AlertManager()
        server = MonitoringHTTPServer(
            host="127.0.0.1",
            port=0,
            health_checker=hc,
            metrics_collector=mc,
            alert_manager=am,
        )

        async def run():
            await server.start_nonblocking()
            port = server._server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET /readyz HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            resp = await reader.readuntil(b"\r\n\r\n")
            status = int(resp.decode().split("\r\n")[0].split(" ")[1])
            self.assertEqual(status, 200)
            await server.stop()

        asyncio.run(run())

    def test_unknown_path_returns_404(self):
        """Test: Unknown path returns 404."""
        self._run_server_test("/unknown", 404)


class TestSLOThresholds(unittest.TestCase):
    """Test specific SLO thresholds defined in requirements."""

    def test_classify_and_remember_p99_under_200ms_ok(self):
        """Test: classify_and_remember under 200ms P99 does NOT trigger alert."""
        mc = MetricsCollector()
        am = AlertManager()
        for _ in range(50):
            mc.record_latency("classify_and_remember", 80.0)
        alerts = am.check_alerts(mc.get_snapshot())
        classify_alerts = [a for a in alerts if "classify" in a.metric_name]
        self.assertEqual(len(classify_alerts), 0)

    def test_classify_and_remember_p99_over_200ms_alerts(self):
        """Test: classify_and_remember over 200ms P99 DOES trigger alert."""
        mc = MetricsCollector()
        am = AlertManager()
        for _ in range(100):
            mc.record_latency("classify_and_remember", 250.0)
        alerts = am.check_alerts(mc.get_snapshot())
        classify_alerts = [a for a in alerts if "classify" in a.metric_name]
        self.assertGreater(len(classify_alerts), 0)

    def test_recall_p99_under_500ms_ok(self):
        """Test: recall under 500ms P99 does NOT trigger alert."""
        mc = MetricsCollector()
        am = AlertManager()
        for _ in range(50):
            mc.record_latency("recall", 200.0)
        alerts = am.check_alerts(mc.get_snapshot())
        recall_alerts = [a for a in alerts if "recall" in a.metric_name]
        self.assertEqual(len(recall_alerts), 0)

    def test_recall_p99_over_500ms_alerts(self):
        """Test: recall over 500ms P99 DOES trigger alert."""
        mc = MetricsCollector()
        am = AlertManager()
        for _ in range(100):
            mc.record_latency("recall", 600.0)
        alerts = am.check_alerts(mc.get_snapshot())
        recall_alerts = [a for a in alerts if "recall" in a.metric_name]
        self.assertGreater(len(recall_alerts), 0)

    def test_startup_under_2s_ok(self):
        """Test: startup under 2000ms does NOT trigger alert."""
        mc = MetricsCollector()
        am = AlertManager()
        for _ in range(10):
            mc.record_latency("startup", 1500.0)
        alerts = am.check_alerts(mc.get_snapshot())
        startup_alerts = [a for a in alerts if "startup" in a.metric_name]
        self.assertEqual(len(startup_alerts), 0)

    def test_startup_over_2s_alerts(self):
        """Test: startup over 2000ms DOES trigger alert."""
        mc = MetricsCollector()
        am = AlertManager()
        for _ in range(10):
            mc.record_latency("startup", 2500.0)
        alerts = am.check_alerts(mc.get_snapshot())
        startup_alerts = [a for a in alerts if "startup" in a.metric_name]
        self.assertGreater(len(startup_alerts), 0)


class TestAlertSeverityLevels(unittest.TestCase):
    """Test different alert severity levels."""

    def test_info_alert_formatted_correctly(self):
        """Test: INFO severity appears in formatted output."""
        alert = Alert(AlertSeverity.INFO, "test", "info msg", 1.0, 2.0)
        fmt = AlertManager.format_alert(alert)
        self.assertIn("INFO", fmt)

    def test_warning_alert_formatted_correctly(self):
        """Test: WARNING severity appears in formatted output."""
        alert = Alert(AlertSeverity.WARNING, "test", "warn msg", 1.0, 2.0)
        fmt = AlertManager.format_alert(alert)
        self.assertIn("WARNING", fmt)

    def test_critical_alert_formatted_correctly(self):
        """Test: CRITICAL severity appears in formatted output."""
        alert = Alert(AlertSeverity.CRITICAL, "test", "crit msg", 1.0, 2.0)
        fmt = AlertManager.format_alert(alert)
        self.assertIn("CRITICAL", fmt)


if __name__ == "__main__":
    unittest.main()
