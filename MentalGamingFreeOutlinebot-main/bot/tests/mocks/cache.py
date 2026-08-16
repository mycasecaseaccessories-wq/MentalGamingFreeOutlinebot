"""Mock cache for testing without real in-memory state."""

from __future__ import annotations

from typing import Any


class MockCache:
    """In-memory dict-backed cache — fully synchronous for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._call_log: list[tuple[str, Any]] = []

    def get(self, key: str, default: Any = None) -> Any:
        self._call_log.append(("get", key))
        return self._store.get(key, default)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._call_log.append(("set", key))
        self._store[key] = value

    def delete(self, key: str) -> bool:
        self._call_log.append(("delete", key))
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        self._call_log.append(("clear", None))
        self._store.clear()

    def exists(self, key: str) -> bool:
        return key in self._store

    # ── Test helpers ──────────────────────────────────────────────────────────

    def was_called_with(self, operation: str, key: str) -> bool:
        """Return True if *operation* was called with *key*."""
        return any(op == operation and k == key for op, k in self._call_log)

    def reset_log(self) -> None:
        self._call_log.clear()

    @property
    def size(self) -> int:
        return len(self._store)
