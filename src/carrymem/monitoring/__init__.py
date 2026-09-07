"""CarryMem Monitoring Framework (MVP).

Provides:
- HealthChecker: /healthz, /readyz endpoint logic
- MetricsCollector: counters, latency histograms, Prometheus export

SLO Targets:
- classify_and_remember P99 < 200ms
- recall P99 < 500ms
- startup time < 2s
"""

import threading
import time
from collections import deque
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

_LATENCY_MAX_SAMPLES = 10_000

# ── Data Classes ──────────────────────────────────────────────────────────


class AlertSeverity(str, Enum):
    """Severity level for monitoring alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


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
        self._latency_buckets: Dict[str, deque] = {}
        self._gauges: Dict[str, float] = {}
        self._start_time: float = time.time()

    def increment(self, operation: str, value: int = 1) -> None:
        """Increment a counter for the given operation."""
        with self._lock:
            self._counters[operation] = self._counters.get(operation, 0) + value

    def record_latency(self, operation: str, ms: float) -> None:
        """Record a latency sample (in milliseconds) for the given operation.

        Samples are retained in a bounded deque (oldest dropped beyond
        ``_LATENCY_MAX_SAMPLES``) so per-operation memory stays constant.
        """
        with self._lock:
            if operation not in self._latency_buckets:
                self._latency_buckets[operation] = deque(maxlen=_LATENCY_MAX_SAMPLES)
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
                lines.append(f'carrymem_latency_ms{{operation="{safe_op}",quantile="0.99"}} {stats.get("p99", 0)}')
                lines.append(f'carrymem_latency_ms{{operation="{safe_op}",quantile="0.95"}} {stats.get("p95", 0)}')
                lines.append(f'carrymem_latency_ms{{operation="{safe_op}",quantile="0.5"}} {stats.get("avg", 0)}')
                latency_sum = round(stats.get("avg", 0) * stats["count"], 2)
                lines.append(f'carrymem_latency_ms_sum{{operation="{safe_op}"}} {latency_sum}')
                lines.append(f'carrymem_latency_ms_count{{operation="{safe_op}"}} {stats["count"]}')

        # Gauges
        if snapshot["gauges"]:
            lines.append("\n# TYPE carrymem_gauge gauge")
            for name, val in snapshot["gauges"].items():
                safe_name = name.replace("-", "_").replace(".", "_")
                lines.append(f"{safe_name} {val}")

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
                slo_status.append(
                    {
                        "operation": slo.operation,
                        "threshold_ms": slo.p99_threshold_ms,
                        "status": "no_data",
                    }
                )

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


__all__ = [
    "AlertSeverity",
    "SLOTarget",
    "_DEFAULT_SLOS",
    "MetricsCollector",
    "HealthChecker",
]
