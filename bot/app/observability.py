"""
Observability — Metrics, Performance Timers, Request IDs, Structured Logging.

Provides the building blocks for monitoring application performance and
tracing requests across the codebase without a heavy external dependency.

Components
----------
  RequestContext  — Holds request_id + correlation_id for one Telegram update.
  Timer           — Context manager that measures and logs execution duration.
  MetricsCollector — In-process counter/gauge store; Prometheus-export-ready.
  request_ctx     — contextvars.ContextVar[RequestContext] for async propagation.

Prometheus compatibility
------------------------
MetricsCollector.export_text() emits the Prometheus text exposition format.
A future /metrics HTTP endpoint can call this directly.

Usage
-----
    from app.observability import Timer, metrics, new_request_context, request_ctx

    # In a middleware — stamp the update with a request ID:
    ctx = new_request_context()
    request_ctx.set(ctx)

    # Time a block:
    async with Timer("db.query.user_lookup"):
        user = await repo.get(telegram_id)

    # Increment a counter:
    metrics.increment("bot.updates.received")

Phase 0.5: Full implementation; no external dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request Context
# ---------------------------------------------------------------------------

@dataclass
class RequestContext:
    """
    Per-request tracing context propagated via contextvars.

    Attributes:
        request_id:     Unique ID for this Telegram update (UUIDv4 short form).
        correlation_id: Optional external correlation ID (e.g. from a webhook
                        header).  Falls back to request_id when not provided.
        started_at:     Monotonic timestamp when the request was created.
        user_id:        Telegram user ID, set by the auth middleware.
        username:       Telegram @username or full name, set by auth middleware.
        language:       Resolved UI language code, set by language middleware.
    """
    request_id:     str   = field(default_factory=lambda: uuid.uuid4().hex[:12])
    correlation_id: str   = field(default="")
    started_at:     float = field(default_factory=time.monotonic)
    user_id:        Optional[int]  = field(default=None)
    username:       Optional[str]  = field(default=None)
    language:       Optional[str]  = field(default=None)
    current_user:   Any = field(default=None, repr=False)
    current_role:   Optional[str] = field(default=None)
    application_user_id: Optional[int] = field(default=None)
    admin_principal_id: Optional[int] = field(default=None)
    chat_id: Optional[int] = field(default=None)
    update_id: Optional[int] = field(default=None)
    callback_query_id: Optional[str] = field(default=None)
    current_settings: Any = field(default=None, repr=False)
    timestamp:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.correlation_id:
            self.correlation_id = self.request_id

    @property
    def elapsed_ms(self) -> float:
        """Milliseconds elapsed since the request was created."""
        return (time.monotonic() - self.started_at) * 1000

    def as_log_extra(self) -> dict[str, Any]:
        """Return a dict suitable for passing as *extra=* to logger calls."""
        return {
            "request_id":     self.request_id,
            "correlation_id": self.correlation_id,
            "user_id":        self.user_id,
            "language":       self.language,
                        "role":           self.current_role,
            "application_user_id": self.application_user_id,
            "admin_principal_id": self.admin_principal_id,
            "chat_id":         self.chat_id,
            "update_id":       self.update_id,
            "callback_query_id": self.callback_query_id,
            "timestamp":       self.timestamp.isoformat(),

        }

    def __repr__(self) -> str:
        return (
            f"RequestContext(id={self.request_id!r} user={self.user_id} "
            f"lang={self.language!r} elapsed={self.elapsed_ms:.1f}ms)"
        )


#: ContextVar that propagates the current RequestContext through async call chains.
#: Set by the request_context middleware at the start of each Telegram update.
request_ctx: ContextVar[Optional[RequestContext]] = ContextVar(
    "request_ctx", default=None
)


def new_request_context(
    correlation_id: str = "",
    user_id: Optional[int] = None,
    language: Optional[str] = None,
) -> RequestContext:
    """
    Create and activate a new RequestContext for the current async task.

    Args:
        correlation_id: Optional external trace ID.
        user_id:        Telegram user ID (may be set later by auth middleware).
        language:       Language code (may be set later by language middleware).

    Returns:
        The newly created and activated RequestContext.
    """
    ctx = RequestContext(
        correlation_id=correlation_id,
        user_id=user_id,
        language=language,
    )
    request_ctx.set(ctx)
    return ctx


def get_request_id() -> str:
    """
    Return the current request ID, or an empty string if none is set.

    Safe to call from any async context; returns "" outside of a request.
    """
    ctx = request_ctx.get()
    return ctx.request_id if ctx else ""


# ---------------------------------------------------------------------------
# Request-ID log filter
# ---------------------------------------------------------------------------

class RequestIdFilter(logging.Filter):
    """
    Logging filter that injects request_id into every LogRecord.

    Install this on any handler to make request_id available in log
    format strings as %(request_id)s.

    Usage (in setup_logging):
        handler.addFilter(RequestIdFilter())
        fmt = "... %(request_id)s ..."
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        record.request_id = get_request_id() or "-"  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# Performance Timer
# ---------------------------------------------------------------------------

class Timer:
    """
    Async context manager that measures and logs execution duration.

    Usage:
        async with Timer("db.user.lookup", threshold_ms=100):
            result = await repo.get_user(42)

    Logs at DEBUG level normally; at WARNING when *threshold_ms* is exceeded.

    Also records the duration in the module-level MetricsCollector as a
    histogram observation under the metric name ``timer.<name>``.
    """

    def __init__(
        self,
        name: str,
        threshold_ms: float = 0.0,
        log_level: int = logging.DEBUG,
    ) -> None:
        self.name = name
        self.threshold_ms = threshold_ms
        self.log_level = log_level
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

    async def __aenter__(self) -> "Timer":
        self._start = time.monotonic()
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.elapsed_ms = (time.monotonic() - self._start) * 1000
        level = (
            logging.WARNING
            if self.threshold_ms and self.elapsed_ms > self.threshold_ms
            else self.log_level
        )
        logger.log(level, "Timer [%s] %.2f ms", self.name, self.elapsed_ms)
        metrics.observe(f"timer.{self.name}", self.elapsed_ms)


@asynccontextmanager
async def timed(name: str, threshold_ms: float = 0.0) -> AsyncIterator[Timer]:
    """
    Functional form of Timer for use with `async with timed("name"):`.

    Args:
        name:         Metric/log label.
        threshold_ms: Log at WARNING if exceeded.

    Yields:
        Timer instance (elapsed_ms available after the block).
    """
    async with Timer(name, threshold_ms) as t:
        yield t


# ---------------------------------------------------------------------------
# Metrics Collector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """
    Lightweight in-process metrics store.

    Supports three metric types:
      counter   — monotonically increasing integer (requests, errors, …).
      gauge     — current numeric value (active users, queue depth, …).
      histogram — list of observed float values (latencies, sizes, …).

    All operations are synchronous and lock-free.  Suitable for single-process
    bots; not shared across workers.

    Prometheus compatibility
    -----------------------
    export_text() outputs the Prometheus text exposition format so a future
    HTTP endpoint can serve it without library changes.
    """

    def __init__(self) -> None:
        self._counters:   dict[str, int]         = defaultdict(int)
        self._gauges:     dict[str, float]        = defaultdict(float)
        self._histograms: dict[str, list[float]]  = defaultdict(list)

    # ── Counters ──────────────────────────────────────────────────────────

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment counter *name* by *amount*."""
        self._counters[name] += amount

    def counter(self, name: str) -> int:
        """Return the current value of counter *name*."""
        return self._counters[name]

    # ── Gauges ────────────────────────────────────────────────────────────

    def set_gauge(self, name: str, value: float) -> None:
        """Set gauge *name* to *value*."""
        self._gauges[name] = value

    def gauge(self, name: str) -> float:
        """Return the current gauge value."""
        return self._gauges[name]

    # ── Histograms ────────────────────────────────────────────────────────

    def observe(self, name: str, value: float) -> None:
        """Record one observation in histogram *name*."""
        self._histograms[name].append(value)

    def histogram_summary(self, name: str) -> dict[str, float]:
        """Return basic stats for histogram *name*."""
        obs = self._histograms.get(name, [])
        if not obs:
            return {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "count": len(obs),
            "sum":   sum(obs),
            "min":   min(obs),
            "max":   max(obs),
            "avg":   sum(obs) / len(obs),
        }

    # ── Snapshot & export ─────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return all metrics as a plain dict (for health/admin endpoints)."""
        return {
            "counters":   dict(self._counters),
            "gauges":     dict(self._gauges),
            "histograms": {
                k: self.histogram_summary(k) for k in self._histograms
            },
        }

    def export_text(self) -> str:
        """
        Export metrics in Prometheus text exposition format.

        Example output:
            # TYPE bot_updates_received counter
            bot_updates_received 42
        """
        lines: list[str] = []

        for name, val in self._counters.items():
            prom_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# TYPE {prom_name} counter")
            lines.append(f"{prom_name} {val}")

        for name, val in self._gauges.items():
            prom_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# TYPE {prom_name} gauge")
            lines.append(f"{prom_name} {val}")

        for name in self._histograms:
            s = self.histogram_summary(name)
            prom_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# TYPE {prom_name} histogram")
            lines.append(f"{prom_name}_count {int(s['count'])}")
            lines.append(f"{prom_name}_sum {s['sum']:.4f}")

        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all metrics (useful in tests)."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

#: Global metrics collector.  Import and call directly from any module.
metrics: MetricsCollector = MetricsCollector()
