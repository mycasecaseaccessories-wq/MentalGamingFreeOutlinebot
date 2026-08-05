---
name: Phase 0.5 infrastructure
description: What was implemented in Phase 0.5 and key design decisions for the Mental VPN Bot.
---

## What was implemented

- `app/lifecycle.py` — `LifecycleManager` singleton with state machine (STARTING → RUNNING → STOPPING → STOPPED). Import `lifecycle` and `AppState`.
- `app/cache.py` — `CacheService` wrapping `MemoryCache` (TTL, pruning, invalidation). Redis-ready via `CacheBackend` ABC. Module-level `cache` singleton.
- `app/observability.py` — `RequestContext` (per-update request_id via ContextVar), `RequestIdFilter` (injects into every LogRecord), `Timer` (async context manager), `MetricsCollector` (counters/gauges/histograms, Prometheus text export). Module-level `metrics` singleton.
- `app/middlewares/request_context.py` — Stamps every Telegram update with a `RequestContext` at group=-2. Stores in `context.user_data["request_context"]`.

## Patched existing files

- `app/utils/directories.py` — added `cache/` and `docs/` to required directories.
- `app/utils/startup_checks.py` — added `check_admin_ids`, `check_scheduler`, `check_cache`; `run_all_checks` now accepts `scheduler` and `cache_service` args.
- `app/services/health_service.py` — added `check_cache` and `check_localization`; `__init__` now accepts `cache` kwarg.
- `app/utils/logger.py` — format string now includes `[%(request_id)s]`; `RequestIdFilter` added to all handlers (imported lazily inside `setup_logging()` to avoid circular imports).
- `app/handlers/error.py` — error classification (telegram/database/configuration/scheduler); error metrics tracking; request_id in log lines.
- `app/middlewares/__init__.py` — exposes `request_context_middleware_handler` and `get_request_context`.
- `app/services/registry.py` — `HealthService` now receives `cache` on creation.
- `main.py` — full 15-step bootstrap; lifecycle transitions; graceful shutdown with ordered teardown.

## Key design decisions

**Why lazy import of RequestIdFilter in setup_logging():**  
`app.observability` → (no circular), but loading it at module import time of `logger.py` could cause issues because `logger.py` is imported before `observability.py` in some code paths. Lazy import avoids this entirely.

**Why request_context middleware runs at group=-2:**  
Must run before auth (group=-1) so request_id is available in all subsequent middlewares for structured logging.

**Why `asyncio.Lock()` in MemoryCache is safe:**  
Python 3.12 removed the requirement for a running event loop at Lock creation time.

**Startup validation order:**  
BOT_TOKEN → ADMIN_IDS → Directories → Configuration → Localisation → Database → Scheduler → Cache. Ordered so cheap sync checks run before expensive async ones.
