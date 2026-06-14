"""CarryMem Monitoring & Alerting Framework (MVP).

Provides:
- HealthChecker: /healthz, /readyz endpoint logic
- MetricsCollector: counters, latency histograms, Prometheus export
- AlertManager: SLO threshold checking with console alerts
- MonitoringHTTPServer: lightweight HTTP server for monitoring endpoints

SLO Targets:
- classify_and_remember P99 < 200ms
- recall P99 < 500ms
- startup time < 2s
"""

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from carrymem.utils.logger import logger


# ── Data Classes ──────────────────────────────────────────────────────────


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a single alert."""

    severity: AlertSeverity
    metric_name: str
    message: str
    threshold: float
    actual_value: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class PluginStatus:
    """Status of a loaded plugin."""

    name: str
    version: str = ""
    loaded: bool = False
    error: Optional[str] = None


# ── SLO Definitions ───────────────────────────────────────────────────────


class SLOTarget:
    """Service Level Objective target definition."""

    def __init__(
        self,
        operation: str,
        metric_type: str,
        p99_threshold_ms: float,
        severity: AlertSeverity = AlertSeverity.WARNING,
    ):
        self.operation = operation
        self.metric_type = metric_type  # "latency" | "counter"
        self.p99_threshold_ms = p99_threshold_ms
        self.severity = severity


_DEFAULT_SLOS: List[SLOTarget] = [
    SLOTarget("classify_and_remember", "latency", 200.0),
    SLOTarget("recall", "latency", 500.0),
    SLOTarget("startup", "latency", 2000.0),
]


# ── Metrics Collector ─────────────────────────────────────────────────────


class MetricsCollector:
    """Thread-safe metrics collector with counters and latency histograms."""

    def __init__(self):
        self._lock = threading.RLock()
        self._counters: Dict[str, int] = {}
        self._latency_buckets: Dict[str, List[float]] = {}
        self._gauges: Dict[str, float] = {}
        self._start_time: float = time.time()

    def increment(self, operation: str, value: int = 1) -> None:
        """Increment a counter for the given operation."""
        with self._lock:
            self._counters[operation] = self._counters.get(operation, 0) + value

    def record_latency(self, operation: str, ms: float) -> None:
        """Record a latency sample (in milliseconds) for the given operation."""
        with self._lock:
            if operation not in self._latency_buckets:
                self._latency_buckets[operation] = []
            self._latency_buckets[operation].append(ms)

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value."""
        with self._lock:
            self._gauges[name] = value

    def get_snapshot(self) -> Dict[str, Any]:
        """Export current metrics snapshot as a dict."""
        with self._lock:
            latency_stats: Dict[str, Dict[str, Any]] = {}
            for op, samples in self._latency_buckets.items():
                if samples:
                    sorted_samples = sorted(samples)
                    n = len(sorted_samples)
                    p99_idx = int(n * 0.99)
                    p99_idx = min(p99_idx, n - 1)
                    latency_stats[op] = {
                        "count": n,
                        "min": round(sorted_samples[0], 3),
                        "max": round(sorted_samples[-1], 3),
                        "avg": round(sum(sorted_samples) / n, 3),
                        "p99": round(sorted_samples[p99_idx], 3),
                        "p95": round(sorted_samples[int(n * 0.95)], 3) if n > 20 else None,
                    }
                else:
                    latency_stats[op] = {"count": 0}

            return {
                "counters": dict(self._counters),
                "latency": latency_stats,
                "gauges": dict(self._gauges),
                "uptime_seconds": round(time.time() - self._start_time, 2),
            }

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        snapshot = self.get_snapshot()
        lines: List[str] = []

        # Counters
        lines.append("# TYPE carrymem_counter counter")
        for op, count in snapshot["counters"].items():
            safe_op = op.replace("-", "_").replace(".", "_")
            lines.append(f'carrymem_total{{operation="{op}"}} {count}')

        # Latency histograms (summary style)
        lines.append("\n# TYPE carrymem_latency_ms summary")
        for op, stats in snapshot["latency"].items():
            if stats.get("count", 0) > 0:
                safe_op = op.replace("-", "_").replace(".", "_")
                lines.append(f'carrymem_latency_ms{{operation="{op}",quantile="0.99"}} {stats.get("p99", 0)}')
                lines.append(f'carrymem_latency_ms{{operation="{op}",quantile="0.95"}} {stats.get("p95", 0)}')
                lines.append(f'carrymem_latency_ms{{operation="{op}",quantile="0.5"}} {stats.get("avg", 0)}')
                lines.append(f'carrymem_latency_ms_sum{{operation="{op}"}} {round(stats.get("avg", 0) * stats["count"], 2)}')
                lines.append(f'carrymem_latency_ms_count{{operation="{op}"}} {stats["count"]}')

        # Gauges
        if snapshot["gauges"]:
            lines.append("\n# TYPE carrymem_gauge gauge")
            for name, val in snapshot["gauges"].items():
                safe_name = name.replace("-", "_").replace(".", "_")
                lines.append(f'{safe_name} {val}')

        lines.append(f"\n# TYPE carrymem_uptime_seconds gauge")
        lines.append(f'carrymem_uptime_seconds {snapshot["uptime_seconds"]}')

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._counters.clear()
            self._latency_buckets.clear()
            self._gauges.clear()


# ── Health Checker ────────────────────────────────────────────────────────


class HealthChecker:
    """Health check endpoint logic.

    Returns overall status based on component checks.
    """

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        slo_targets: Optional[List[SLOTarget]] = None,
    ):
        self._metrics = metrics_collector or MetricsCollector()
        self._slo_targets = slo_targets or _DEFAULT_SLOS
        self._ready: bool = False
        self._checks: Dict[str, Callable[[], bool]] = {}

    def register_check(self, name: str, check_fn: Callable[[], bool]) -> None:
        """Register a custom health check function."""
        self._checks[name] = check_fn

    def set_ready(self, ready: bool = True) -> None:
        """Set readiness state."""
        self._ready = ready

    def check(self) -> Dict[str, Any]:
        """Run all health checks and return status.

        Returns:
            {"status": "ok"|"degraded", "checks": {...}, ...}
        """
        checks_result: Dict[str, Any] = {}
        degraded = False

        # Run registered checks
        for name, fn in self._checks.items():
            try:
                passed = fn()
                checks_result[name] = {"status": "ok" if passed else "fail"}
                if not passed:
                    degraded = True
            except Exception as e:
                checks_result[name] = {"status": "error", "message": str(e)}
                degraded = True

        # SLO checks
        slo_status: List[Dict[str, Any]] = []
        snapshot = self._metrics.get_snapshot()
        for slo in self._slo_targets:
            lat_stats = snapshot["latency"].get(slo.operation, {})
            p99_val = lat_stats.get("p99")
            if p99_val is not None:
                within_slo = p99_val <= slo.p99_threshold_ms
                entry: Dict[str, Any] = {
                    "operation": slo.operation,
                    "threshold_ms": slo.p99_threshold_ms,
                    "p99_actual_ms": p99_val,
                    "within_slo": within_slo,
                }
                if not within_slo:
                    degraded = True
                    entry["severity"] = slo.severity.value
                slo_status.append(entry)
            else:
                slo_status.append({
                    "operation": slo.operation,
                    "threshold_ms": slo.p99_threshold_ms,
                    "status": "no_data",
                })

        status = "degraded" if degraded else "ok"
        return {
            "status": status,
            "checks": checks_result,
            "slo": slo_status,
            "uptime_seconds": snapshot["uptime_seconds"],
        }

    def readyz(self) -> Dict[str, Any]:
        """Return readiness status."""
        return {
            "status": "ready" if self._ready else "not_ready",
            "ready": self._ready,
        }


# ── Alert Manager ─────────────────────────────────────────────────────────


class AlertManager:
    """Alert manager (MVP: console-only output).

    Checks metrics against SLO thresholds and generates alerts.
    """

    def __init__(
        self,
        slo_targets: Optional[List[SLOTarget]] = None,
    ):
        self._slo_targets = slo_targets or _DEFAULT_SLOS
        self._alert_history: List[Alert] = []
        self._lock = threading.Lock()

    def check_alerts(self, metrics_snapshot: Dict[str, Any]) -> List[Alert]:
        """Check metrics snapshot against SLO thresholds.

        Args:
            metrics_snapshot: Output of MetricsCollector.get_snapshot().

        Returns:
            List of triggered Alerts.
        """
        alerts: List[Alert] = []
        lat_data = metrics_snapshot.get("latency", {})

        for slo in self._slo_targets:
            stats = lat_data.get(slo.operation, {})
            p99_val = stats.get("p99")
            if p99_val is not None and p99_val > slo.p99_threshold_ms:
                alert = Alert(
                    severity=slo.severity,
                    metric_name=f"{slo.operation}_p99_latency",
                    message=(
                        f"SLO violation: {slo.operation} P99 latency "
                        f"{p99_val:.1f}ms exceeds threshold {slo.p99_threshold_ms:.0f}ms"
                    ),
                    threshold=slo.p99_threshold_ms,
                    actual_value=p99_val,
                )
                alerts.append(alert)

        with self._lock:
            self._alert_history.extend(alerts)

        for alert in alerts:
            formatted = self.format_alert(alert)
            if alert.severity == AlertSeverity.CRITICAL:
                logger.critical(formatted)
            elif alert.severity == AlertSeverity.WARNING:
                logger.warning(formatted)
            else:
                logger.info(formatted)

        return alerts

    @staticmethod
    def format_alert(alert: Alert) -> str:
        """Format an alert as a human-readable string."""
        return (
            f"[ALERT:{alert.severity.value.upper()}] "
            f"{alert.metric_name}: {alert.message} "
            f"(threshold={alert.threshold:.0f}ms, actual={alert.actual_value:.1f}ms)"
        )

    def get_alert_history(self) -> List[Alert]:
        """Return all recorded alerts."""
        with self._lock:
            return list(self._alert_history)

    def clear_history(self) -> None:
        """Clear alert history (for testing)."""
        with self._lock:
            self._alert_history.clear()


# ── Monitoring HTTP Server ────────────────────────────────────────────────


class MonitoringHTTPServer:
    """Lightweight async HTTP server for monitoring endpoints.

    Endpoints:
        GET /healthz  → JSON health status
        GET /metrics  → Prometheus text format
        GET /readyz   → Readiness probe
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8766,
        health_checker: Optional[HealthChecker] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        alert_manager: Optional[AlertManager] = None,
    ):
        self._host = host
        self._port = port
        self._health_checker = health_checker or HealthChecker()
        self._metrics = metrics_collector or MetricsCollector()
        self._alert_manager = alert_manager or AlertManager()
        # Wire shared instances
        if health_checker is None:
            self._health_checker = HealthChecker(
                metrics_collector=self._metrics,
            )
        self._server = None

    async def _handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle a single HTTP request."""
        try:
            request_line = await reader.readline()
            if not request_line:
                writer.close()
                return

            request_str = request_line.decode("utf-8", errors="replace").strip()
            parts = request_str.split(" ")
            if len(parts) < 2:
                writer.close()
                return

            method = parts[0]
            path = parts[1].split("?")[0]  # strip query string

            # Consume headers
            while True:
                line = await reader.readline()
                if not line or line == b"\r\n":
                    break

            # Route
            if method == "GET":
                if path == "/healthz":
                    body = self._health_checker.check()
                    # Also run alert check
                    snapshot = self._metrics.get_snapshot()
                    self._alert_manager.check_alerts(snapshot)
                    await self._json_response(writer, 200, body)
                elif path == "/metrics":
                    text = self._metrics.to_prometheus()
                    await self._text_response(writer, 200, text)
                elif path == "/readyz":
                    body = self._health_checker.readyz()
                    await self._json_response(writer, 200, body if body["ready"] else (body, 503))
                else:
                    await self._json_response(writer, 404, {"error": "Not found"})
            else:
                await self._json_response(writer, 405, {"error": "Method not allowed"})
        except Exception as e:
            logger.error("Monitoring request error: %s", e, exc_info=True)
            try:
                await self._json_response(writer, 500, {"error": "Internal server error"})
            except (OSError, ConnectionError):
                pass
        finally:
            try:
                writer.close()
            except (OSError, ConnectionError):
                pass

    async def _json_response(self, writer, status_code: int, body) -> None:
        """Send a JSON HTTP response."""
        actual_body = body[0] if isinstance(body, tuple) else body
        actual_status = body[1] if isinstance(body, tuple) else status_code
        body_bytes = json.dumps(actual_body).encode("utf-8")
        headers = (
            f"HTTP/1.1 {actual_status} {'OK' if actual_status == 200 else 'Error'}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "\r\n"
        )
        writer.write(headers.encode() + body_bytes)
        await writer.drain()

    async def _text_response(self, writer, status_code: int, text: str) -> None:
        """Send a plain text HTTP response."""
        body_bytes = text.encode("utf-8")
        headers = (
            f"HTTP/1.1 {status_code} OK\r\n"
            "Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "\r\n"
        )
        writer.write(headers.encode() + body_bytes)
        await writer.drain()

    async def start(self) -> None:
        """Start the monitoring HTTP server (blocks until stop())."""
        self._server = await asyncio.start_server(
            self._handle_request, self._host, self._port,
        )
        addrs = ", ".join(str(s.getsockname()) for s in self._server.sockets)
        logger.info("Monitoring server running on %s", addrs)
        async with self._server:
            await self._server.serve_forever()

    async def start_nonblocking(self) -> None:
        """Start the monitoring HTTP server without blocking.

        The server runs as a background task. Use stop() to shut it down.
        """
        self._server = await asyncio.start_server(
            self._handle_request, self._host, self._port,
        )
        addrs = ", ".join(str(s.getsockname()) for s in self._server.sockets)
        logger.info("Monitoring server running on %s", addrs)
        # Run serve_forever in a background task so it doesn't block
        self._serve_task = asyncio.create_task(self._server.serve_forever())

    async def stop(self) -> None:
        """Stop the monitoring HTTP server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if hasattr(self, '_serve_task') and self._serve_task:
            self._serve_task.cancel()
            try:
                await self._serve_task
            except asyncio.CancelledError:
                pass
        logger.info("Monitoring server stopped")

    @property
    def health_checker(self) -> HealthChecker:
        return self._health_checker

    @property
    def metrics_collector(self) -> MetricsCollector:
        return self._metrics

    @property
    def alert_manager(self) -> AlertManager:
        return self._alert_manager


# ── Convenience: context manager for latency tracking ──────────────────────


class LatencyTimer:
    """Context manager to record operation latency."""

    def __init__(self, collector: MetricsCollector, operation: str):
        self._collector = collector
        self._operation = operation
        self._start: float = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ms = (time.monotonic() - self._start) * 1000
        self._collector.record_latency(self._operation, ms)
        return False


__all__ = [
    # Data classes
    "AlertSeverity",
    "Alert",
    "PluginStatus",
    # SLO
    "SLOTarget",
    "_DEFAULT_SLOS",
    # Core components
    "MetricsCollector",
    "HealthChecker",
    "AlertManager",
    "MonitoringHTTPServer",
    # Utilities
    "LatencyTimer",
]
