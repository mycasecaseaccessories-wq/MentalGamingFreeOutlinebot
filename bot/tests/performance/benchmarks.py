"""
Performance benchmarks for the Mental VPN Platform.

Run with:
    pytest bot/tests/performance/ -v -m performance

These tests measure execution time and flag regressions.
They do NOT assert functionality — only speed.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator


@contextmanager
def timed(label: str, max_ms: float = 100.0) -> Generator[None, None, None]:
    """Context manager that asserts code runs within *max_ms* milliseconds."""
    start = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms <= max_ms, (
        f"[PERF] {label} took {elapsed_ms:.2f}ms — exceeded budget of {max_ms:.0f}ms"
    )


class BenchmarkResult:
    """Store benchmark results for reporting."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.runs: list[float] = []

    def record(self, elapsed_ms: float) -> None:
        self.runs.append(elapsed_ms)

    @property
    def avg_ms(self) -> float:
        return sum(self.runs) / len(self.runs) if self.runs else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.runs) if self.runs else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.runs) if self.runs else 0.0

    def __repr__(self) -> str:
        return (
            f"BenchmarkResult({self.label!r}: "
            f"avg={self.avg_ms:.2f}ms, "
            f"min={self.min_ms:.2f}ms, "
            f"max={self.max_ms:.2f}ms, "
            f"runs={len(self.runs)})"
        )
