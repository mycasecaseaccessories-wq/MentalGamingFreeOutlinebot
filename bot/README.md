# Mental Outline VPN Platform

A scalable, commercial Telegram VPN bot powered by [Outline VPN](https://getoutline.org/).

> **Phase 0.6 — Core Foundation, Shared Components & Developer Standards**
> Reusable enums, DTOs, response/pagination contracts, cache tags, event types,
> request context fields, security helpers, and project standards are in place.

---

## Tech Stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Language     | Python 3.12+                        |
| Bot Framework| python-telegram-bot v21             |
| Database     | SQLite (dev) / PostgreSQL (prod)    |
| ORM          | SQLAlchemy 2 async + Alembic        |
| Validation   | Pydantic v2                         |
| Scheduler    | APScheduler 3 (AsyncIOScheduler)    |
| Cache        | In-memory TTL cache (Redis-ready)   |
| VPN          | Outline VPN (Phase 4)               |

---

## Project Structure

```
bot/
├── main.py                   # Application entry point — 15-step bootstrap
├── requirements.txt
├── .env.example              # Environment variable template
│
├── config/
│   ├── settings.py           # Centralised config (reads env vars)
│   ├── defaults.py           # Default setting values
│   └── feature_flags.py     # Feature flag definitions
│
├── app/
│   ├── lifecycle.py          # AppState machine (Starting/Running/Stopping/Stopped)
│   ├── cache.py              # CacheService — TTL memory cache, Redis-ready interface
│   ├── events.py             # Async pub/sub EventBus (APP_STARTED, USER_REGISTERED, …)
│   ├── observability.py      # Metrics, Timer, Request ID, Correlation ID
│   │
│   ├── handlers/
│   │   ├── base.py           # Decorators: admin_only, log_handler
│   │   ├── start.py          # /start, /help
│   │   ├── admin.py          # /admin
│   │   └── error.py          # Global error handler (classifies: telegram/db/config/scheduler)
│   │
│   ├── services/
│   │   ├── registry.py       # ServiceRegistry — DI container, one instance per service
│   │   ├── health_service.py # HealthService — App/DB/Scheduler/Cache/Config/Localisation
│   │   ├── user_service.py
│   │   ├── language_service.py
│   │   ├── settings_service.py
│   │   ├── preference_service.py
│   │   └── …                 # Stubs for Phase 1+ services
│   │
│   ├── repositories/         # Data access layer (repository pattern)
│   ├── models/               # Domain models and enums
│   ├── keyboards/            # Telegram keyboard builders
│   │
│   ├── middlewares/
│   │   ├── request_context.py  # Stamps request_id on every update (group=-2)
│   │   ├── auth.py             # Authentication, user registration (group=-1)
│   │   ├── language.py         # Language resolution, Translator injection (group=-1)
│   │   ├── activity.py         # last_active timestamp (group=-1)
│   │   ├── role.py             # Role checks (used inside handler decorators)
│   │   └── logging.py          # Logging middleware
│   │
│   ├── utils/
│   │   ├── logger.py           # Logging: console + daily rotation + request_id filter
│   │   ├── startup_checks.py   # Pre-flight: BOT_TOKEN, ADMIN_IDS, DB, Dirs, Locales, Cache
│   │   ├── directories.py      # Auto-creates: logs/, database/, backups/, temp/, uploads/, cache/, docs/
│   │   └── helpers.py          # escape_html, truncate, format_bytes
│   │
│   └── scheduler/
│       └── base.py             # APScheduler wrapper (no jobs yet — Phase 4)
│
├── database/
│   ├── connection.py           # Async SQLAlchemy engine + session factory
│   ├── base.py                 # Declarative ORM base class
│   ├── models/                 # ORM models (user, role, setting, wallet, …)
│   ├── repositories/           # SQL query implementations
│   └── migrations/
│       └── versions/           # Alembic migrations 0001–0004
│
├── locales/
│   ├── translator.py           # t() function, Translator class, fallback logic
│   ├── en/                     # English translations
│   └── my/                     # Myanmar translations
│
└── logs/                       # Auto-created; gitignored
```

---

## Quick Start

### 1. Install dependencies

```bash
cd bot
pip install -r requirements.txt
```

### 2. Configure environment

On **Replit**: add secrets via the **Secrets** panel (padlock icon).

Locally:

```bash
cp .env.example .env
# Edit .env — set BOT_TOKEN and ADMIN_IDS at minimum
```

### 3. Run

```bash
python main.py
```

---

## Environment Variables

| Variable           | Required | Default                             | Description                                    |
|--------------------|----------|-------------------------------------|------------------------------------------------|
| `BOT_TOKEN`        | ✅        | —                                   | Telegram bot token from @BotFather             |
| `ADMIN_IDS`        | ✅        | —                                   | Comma-separated Telegram user IDs              |
| `SESSION_SECRET`   | ✅        | —                                   | Long random string for token signing           |
| `DATABASE_URL`     | ❌        | `sqlite+aiosqlite:///./data/…`      | SQLAlchemy async connection URL                |
| `ENVIRONMENT`      | ❌        | `development`                       | `development` / `staging` / `production`       |
| `DEFAULT_LANGUAGE` | ❌        | `en`                                | Default UI language (`en` / `my`)              |
| `LOG_LEVEL`        | ❌        | `INFO`                              | `DEBUG` / `INFO` / `WARNING` / `ERROR`         |
| `TIMEZONE`         | ❌        | `Asia/Yangon`                       | IANA timezone for display and scheduling       |

---

## Startup Flow (15 Steps)

```
 1. Load env vars (dotenv / OS environment)
 2. Load configuration (Settings — fails loudly if BOT_TOKEN missing)
 3. Initialise logger (console + daily rotating file + request_id filter)
 4. Initialise database (run Alembic migrations to HEAD)
 5. Initialise cache (MemoryCache with TTL + background pruning)
 6. Initialise service registry (SettingsService, LanguageService, UserService, …)
 7. Load localisation (Translator warm-up for 'en' and 'my')
 8. Register event bus subscribers (APP_STARTED, APP_STOPPED)
 9. Initialise scheduler (APScheduler — no jobs yet)
10. Register middlewares (request_context @ group=-2; auth/language/activity @ group=-1)
11. Register handlers (start, admin)
12. Register global error handler (must be last)
13. Run startup health check (BOT_TOKEN, ADMIN_IDS, DB, Dirs, Locales, Scheduler, Cache)
14. Lifecycle → RUNNING
15. Start Telegram bot (polling)
```

---

## Application Lifecycle

The `LifecycleManager` (`app/lifecycle.py`) tracks application state:

| State       | Meaning                                         |
|-------------|-------------------------------------------------|
| STARTING    | Bootstrap running — not yet ready for updates   |
| RUNNING     | Fully operational                               |
| MAINTENANCE | Degraded — accepts updates, may respond slowly  |
| STOPPING    | Graceful shutdown in progress                   |
| STOPPED     | All resources released                          |

Subscribe to transitions:

```python
from app.lifecycle import lifecycle, AppState

@lifecycle.on_transition(AppState.STOPPING)
async def save_state(**_):
    ...
```

---

## Graceful Shutdown

On `Ctrl+C` or `SIGTERM`:

```
a. Stop Telegram updater (no new updates accepted)
b. Finish in-flight handlers
c. Stop scheduler (wait for running jobs)
d. Stop cache background tasks
e. Close database connections
f. Emit APP_STOPPED event
g. Lifecycle → STOPPED
h. Flush log handlers
```

---

## Service Registry

`ServiceRegistry` (`app/services/registry.py`) is a lightweight DI container — each service class is instantiated exactly once:

```python
# In any handler:
registry = context.bot_data["registry"]
user_svc = registry.get(UserService)
```

---

## Health Check

`HealthService.check_all()` reports subsystem health:

| Subsystem      | What is checked                        |
|----------------|----------------------------------------|
| Configuration  | BOT_TOKEN present, environment valid   |
| Localisation   | `en` and `my` locale files loadable    |
| Database       | `SELECT 1` query succeeds              |
| Scheduler      | APScheduler is running                 |
| Cache          | Backend is initialised                 |
| Telegram Bot   | `getMe()` call succeeds (network)      |

Future (Phase 3+): Outline Server, Mini App.

---

## Observability

`app/observability.py` provides:

- **RequestContext** — per-update `request_id` + `correlation_id` (propagated via `contextvars`).
- **Timer** — async context manager that measures and logs execution duration.
- **MetricsCollector** — counters, gauges, histograms; `export_text()` emits Prometheus format.
- **RequestIdFilter** — injects `request_id` into every log line automatically.

```python
from app.observability import Timer, metrics

async with Timer("db.user.lookup", threshold_ms=100):
    user = await repo.get(telegram_id)

metrics.increment("bot.updates.received")
```

---

## Cache

`app/cache.py` — TTL-aware in-memory cache with a Redis-compatible interface:

```python
from app.cache import cache

await cache.set("user:42:lang", "en", ttl=300)
lang = await cache.get("user:42:lang")
val  = await cache.get_or_set("key", factory=fetch_fn, ttl=60)
await cache.clear(prefix="user:42:")
```

Drop-in Redis support: replace `MemoryCache` with a `RedisCache(CacheBackend)` in the registry — no call-site changes required.

---

## Event Bus

`app/events.py` — async pub/sub:

```python
from app.events import bus, EventType

@bus.on(EventType.USER_REGISTERED)
async def welcome(telegram_id: int, **_):
    ...

await bus.emit(EventType.USER_REGISTERED, telegram_id=42)
```

---

## Middleware Registration Order

| Group | Middleware              | Purpose                                       |
|-------|-------------------------|-----------------------------------------------|
| -2    | `request_context`       | Stamp `request_id` — must run first           |
| -1    | `auth`                  | Resolve `platform_user`, block banned users   |
| -1    | `language`              | Attach `Translator` to context                |
| -1    | `activity`              | Stamp `last_active` timestamp                 |
| 0+    | handlers                | Business logic                                |

---

## Logging

Every log line includes `request_id`:

```
2025-08-05 12:00:00 | INFO     | __main__:main | [a3f9c1b2e4d7] Bot is running.
```

Log files:
- `logs/bot.log`       — size-based rotation (10 MB × 5 backups)
- `logs/bot_daily.log` — daily rotation (30 days archive)

---

## Developer Modes

Controlled by `ENVIRONMENT`:

| Mode          | Console level | Temp cleared | Admin notifications |
|---------------|---------------|--------------|---------------------|
| `development` | DEBUG         | ✅ on start  | ❌                  |
| `staging`     | INFO          | ❌           | ✅                  |
| `production`  | INFO          | ❌           | ✅                  |

---

## Development Phases

| Phase | Scope                                          | Status       |
|-------|------------------------------------------------|--------------|
| 0.1   | Foundation, architecture, scaffolding          | ✅ Complete  |
| 0.2   | Auth middleware, database migrations           | ✅ Complete  |
| 0.3   | Settings service, category column              | ✅ Complete  |
| 0.4   | Role system, authentication, multi-language    | ✅ Complete  |
| 0.5   | Bootstrap, lifecycle, cache, observability     | ✅ Complete  |
| 0.6   | Shared foundation, DTOs, contracts, standards  | ✅ Complete  |
| 1     | User registration, language selection          | 📋 Planned   |
| 2     | Packages catalogue, admin UI                   | 📋 Planned   |
| 3     | Wallet, payments                               | 📋 Planned   |
| 4     | Outline VPN server & key management            | 📋 Planned   |
| 5     | Referral & affiliate system                    | 📋 Planned   |

---

## Architecture Principles

- **SOLID** — each class has a single responsibility; services depend on repository abstractions.
- **Repository pattern** — all SQL lives in `repositories/`; services never write queries.
- **Async throughout** — every I/O operation (DB, HTTP, Telegram) is async/await.
- **Config by environment** — no hardcoded secrets; all values come from env vars.
- **Fail loudly** — missing required env vars and failed startup checks exit cleanly with a clear message.
- **Observable** — every request carries a `request_id`; metrics are collected automatically.
- **Extensible** — add a handler, service, or event subscriber without modifying existing code.
