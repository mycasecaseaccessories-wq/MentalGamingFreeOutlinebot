"""
Cache Foundation.

An in-memory TTL cache with a Redis-compatible interface so that swapping
in Redis later requires only changing the backend, not the call sites.

Design
------
  • CacheBackend  — abstract interface (get / set / delete / clear / exists).
  • MemoryCache   — in-process dict-based implementation with TTL support.
  • CacheService  — thin wrapper around a backend; registered in ServiceRegistry.

Redis compatibility
-------------------
A future RedisCache(CacheBackend) can be dropped in by changing one line
in ServiceRegistry without touching any code that calls cache.get() / set().

Usage
-----
    from app.cache import cache

    await cache.set("user:42:lang", "en", ttl=300)
    lang = await cache.get("user:42:lang")          # "en" or None
    await cache.delete("user:42:lang")
    await cache.clear(prefix="user:42:")

Phase 0.5: Full in-memory implementation; Redis-ready interface.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------

class CacheBackend(ABC):
    """
    Abstract cache backend interface.

    All cache backends must implement these methods so that CacheService
    is backend-agnostic.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or None if missing/expired."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store *value* under *key*.

        Args:
            key:   Cache key.
            value: Any picklable Python value.
            ttl:   Time-to-live in seconds.  None means no expiry.
        """

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Remove *key* from the cache.  Return True if it existed."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if *key* exists and has not expired."""

    @abstractmethod
    async def clear(self, prefix: Optional[str] = None) -> int:
        """
        Remove cache entries.

        Args:
            prefix: If given, only remove keys starting with this string.
                    If None, remove all entries.

        Returns:
            Number of keys removed.
        """

    @abstractmethod
    async def size(self) -> int:
        """Return the number of unexpired entries in the cache."""


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------

class _Entry:
    """Single cache entry with optional expiry timestamp."""
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: Optional[int]) -> None:
        self.value = value
        self.expires_at: Optional[float] = (time.monotonic() + ttl) if ttl else None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() >= self.expires_at


class MemoryCache(CacheBackend):
    """
    Thread-safe, TTL-aware in-process cache.

    Entries are stored in a plain dict.  Expired entries are lazily evicted
    on access and proactively pruned by a background task (when enabled).

    Args:
        max_size:     Maximum number of entries.  Oldest entries are evicted
                      when the limit is reached.  0 means unlimited.
        prune_every:  Background pruning interval in seconds.  0 disables it.
    """

    def __init__(self, max_size: int = 0, prune_every: int = 60) -> None:
        self._store: dict[str, _Entry] = {}
        self._max_size = max_size
        self._prune_every = prune_every
        self._lock = asyncio.Lock()
        self._prune_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    # ── Backend interface ─────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._store[key]
                return None
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            # Evict oldest entry if at capacity.
            if self._max_size and len(self._store) >= self._max_size:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
                logger.debug("MemoryCache: evicted oldest key %r (max_size=%d)", oldest_key, self._max_size)
            self._store[key] = _Entry(value, ttl)
            logger.debug("MemoryCache: set %r ttl=%s", key, ttl)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            existed = key in self._store
            self._store.pop(key, None)
            return existed

    async def exists(self, key: str) -> bool:
        value = await self.get(key)
        return value is not None

    async def clear(self, prefix: Optional[str] = None) -> int:
        async with self._lock:
            if prefix is None:
                count = len(self._store)
                self._store.clear()
                logger.info("MemoryCache: cleared all %d entries", count)
                return count
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            logger.debug("MemoryCache: cleared %d entries with prefix %r", len(keys), prefix)
            return len(keys)

    async def size(self) -> int:
        async with self._lock:
            # Count only non-expired entries.
            now = time.monotonic()
            return sum(
                1 for e in self._store.values()
                if e.expires_at is None or e.expires_at > now
            )

    # ── Pruning ───────────────────────────────────────────────────────────

    def start_pruning(self) -> None:
        """Start a background task that evicts expired entries periodically."""
        if self._prune_every <= 0:
            return
        if self._prune_task and not self._prune_task.done():
            return
        self._prune_task = asyncio.create_task(self._prune_loop())
        logger.debug("MemoryCache: background pruning started (interval=%ds)", self._prune_every)

    def stop_pruning(self) -> None:
        """Cancel the background pruning task."""
        if self._prune_task and not self._prune_task.done():
            self._prune_task.cancel()
            logger.debug("MemoryCache: background pruning stopped")

    async def _prune_loop(self) -> None:
        while True:
            await asyncio.sleep(self._prune_every)
            await self._prune_expired()

    async def _prune_expired(self) -> int:
        async with self._lock:
            expired = [k for k, e in self._store.items() if e.is_expired()]
            for k in expired:
                del self._store[k]
            if expired:
                logger.debug("MemoryCache: pruned %d expired entries", len(expired))
            return len(expired)

    # ── Invalidation helpers ──────────────────────────────────────────────

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Remove all keys containing *pattern* as a substring.

        More flexible than prefix-based clear(); useful for invalidating
        a user's cached data regardless of key structure.

        Args:
            pattern: Substring to match against cache keys.

        Returns:
            Number of keys removed.
        """
        async with self._lock:
            keys = [k for k in self._store if pattern in k]
            for k in keys:
                del self._store[k]
            if keys:
                logger.debug("MemoryCache: invalidated %d keys matching %r", len(keys), pattern)
            return len(keys)


# ---------------------------------------------------------------------------
# CacheService — thin wrapper registered in ServiceRegistry
# ---------------------------------------------------------------------------

class CacheService:
    """
    Application-level cache service.

    Wraps a CacheBackend and adds:
      • Key namespacing (optional prefix).
      • get_or_set() helper for read-through caching.
      • stats() for health/observability reporting.

    Usage:
        cache = CacheService(MemoryCache())
        await cache.set("key", value, ttl=60)
        val = await cache.get("key")
    """

    def __init__(
        self,
        backend: Optional[CacheBackend] = None,
        namespace: str = "",
    ) -> None:
        self._backend: CacheBackend = backend or MemoryCache()
        self._namespace = namespace
        self._hits = 0
        self._misses = 0

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}" if self._namespace else key

    # ── Public interface (mirrors CacheBackend) ───────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        value = await self._backend.get(self._key(key))
        if value is None:
            self._misses += 1
        else:
            self._hits += 1
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        await self._backend.set(self._key(key), value, ttl)

    async def delete(self, key: str) -> bool:
        return await self._backend.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        return await self._backend.exists(self._key(key))

    async def clear(self, prefix: Optional[str] = None) -> int:
        ns_prefix = self._key(prefix) if prefix else (self._namespace or None)
        return await self._backend.clear(prefix=ns_prefix)

    async def get_or_set(
        self,
        key: str,
        factory: Any,          # Callable[[], Awaitable[Any]]
        ttl: Optional[int] = None,
    ) -> Any:
        """
        Return the cached value, or call *factory* to compute and cache it.

        Args:
            key:     Cache key.
            factory: Async callable that returns the value to cache.
            ttl:     Time-to-live in seconds.

        Returns:
            The cached or freshly computed value.
        """
        value = await self.get(key)
        if value is None:
            value = await factory()
            await self.set(key, value, ttl)
        return value

    # ── Stats ─────────────────────────────────────────────────────────────

    async def stats(self) -> dict[str, Any]:
        """Return cache statistics for health reporting."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total else 0.0
        return {
            "size":     await self._backend.size(),
            "hits":     self._hits,
            "misses":   self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "backend":  type(self._backend).__name__,
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background maintenance tasks (pruning, etc.)."""
        if isinstance(self._backend, MemoryCache):
            self._backend.start_pruning()
        logger.info("CacheService started — backend=%s", type(self._backend).__name__)

    def stop(self) -> None:
        """Stop background maintenance tasks."""
        if isinstance(self._backend, MemoryCache):
            self._backend.stop_pruning()
        logger.info("CacheService stopped")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: Default application cache.  Import and use directly, or replace
#: the backend in Bootstrap for Redis in production.
cache: CacheService = CacheService(MemoryCache(prune_every=120))
