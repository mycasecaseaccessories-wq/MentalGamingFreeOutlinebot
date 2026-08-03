# Mental Outline VPN Platform

A scalable, commercial Telegram VPN platform powered by Outline VPN. Phase 0.1 — project foundation and architecture.

## Run & Operate

- `cd bot && python main.py` — run the Telegram bot (managed by the "Mental VPN Bot" workflow)
- `pnpm --filter @workspace/api-server run dev` — run the Node.js API server (port 5000)
- `pnpm run typecheck` — full TypeScript typecheck across all packages

## Stack

- **Bot:** Python 3.13, python-telegram-bot v21, SQLAlchemy 2 async, aiosqlite, APScheduler, Pydantic v2
- **API:** Node.js 24, Express 5, TypeScript 5.9
- **DB (bot):** SQLite (dev, at `bot/data/mental_vpn.db`) — override with `BOT_DATABASE_URL` for PostgreSQL

## Where things live

```
bot/                         ← Telegram bot (Python)
  main.py                    ← Entry point
  config/settings.py         ← All env-var config (source of truth)
  app/handlers/              ← Telegram update handlers
  app/services/              ← Business logic stubs (7 services)
  app/repositories/          ← Compatibility shims → database/repositories/
  app/models/                ← Domain models + enums (UserRole, Language)
  app/keyboards/             ← Inline keyboard builders
  app/middlewares/           ← Auth + logging middleware stubs
  app/utils/logger.py        ← Rotating file + console logging
  app/scheduler/             ← APScheduler wrapper
  database/
    base.py                  ← DeclarativeBase + BaseModel (id, created_at, updated_at)
    connection.py            ← DatabaseManager singleton (async SQLAlchemy engine)
    session.py               ← get_session() context manager
    models/                  ← 13 ORM models (users, roles, packages, servers,
                             │   vpn_keys, orders, wallets, transactions,
                             │   referrals, free_trials, settings,
                             │   notifications, audit_logs)
    repositories/            ← 9 async repositories with typed CRUD
    migrations/              ← Alembic migration scripts (Phase 0.3)
  locales/                   ← i18n system (en + my translations)
  data/                      ← SQLite database file (dev)
artifacts/api-server/        ← Node.js Express API (separate service)
```

## Architecture decisions

- **BOT_DATABASE_URL** (not DATABASE_URL) — keeps bot's SQLite separate from the Node.js server's Postgres; auto-upgrades sync URL schemes to async equivalents.
- **BaseModel** — every ORM table inherits `id` / `created_at` / `updated_at` from `database/base.py`; no table is missing audit timestamps.
- **Repository pattern** — all SQL lives in `database/repositories/`; services never write queries directly. `app/repositories/` is a compatibility shim that re-exports from there.
- **All models imported in `database/__init__.py`** — guarantees `Base.metadata.create_all()` discovers every table at startup; never skip this import chain.
- **Handlers register via `register(app)`** — each handler module exports a single function; main.py wires them all up. Adding a new group = one import + one call.
- **Service stubs with `NotImplementedError`** — every future service method is scaffolded with a phase tag (e.g. `# TODO (Phase 1)`) so the roadmap is visible in code.
- **Logging** — rotating file handler (5 × 10 MB) in `bot/logs/bot.log` + console; set LOG_LEVEL env var to control verbosity.

## Product

Telegram bot that sells and provisions Outline VPN access keys to customers. Supports multiple languages (English + Myanmar), role-based access (Admin / Customer), wallet top-up, and automated key lifecycle management.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Required secrets (Replit Secrets panel)

| Secret | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `ADMIN_IDS` | Comma-separated Telegram user IDs with admin access |

## Optional env vars

| Variable | Default | Description |
|---|---|---|
| `BOT_DATABASE_URL` | SQLite file | Override DB for the bot |
| `DEFAULT_LANGUAGE` | `en` | New-user default (`en` / `my`) |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `ENVIRONMENT` | `development` | `development` / `production` |

## Gotchas

- Never read `DATABASE_URL` in bot code — Replit manages it for the Node.js Postgres instance. Use `BOT_DATABASE_URL` instead.
- Always run `await db.init()` before using any repository — this applies schema migrations via `create_all`.
- python-telegram-bot v21 requires Python 3.12+; running on 3.13.

## Development Phases

| Phase | Scope | Status |
|---|---|---|
| 0.1 | Foundation, architecture, scaffolding | ✅ Complete |
| 0.2 | Database layer — 13 ORM models, 9 repositories, session module | ✅ Complete |
| 0.3 | Alembic migrations, auth middleware, UserORM → User domain mapping | 🔜 Next |
| 1 | User registration, language selection, main menu | 📋 Planned |
| 2 | Packages catalogue, admin UI | 📋 Planned |
| 3 | Wallet, payments | 📋 Planned |
| 4 | Outline VPN server & key management | 📋 Planned |
| 5 | Referral & affiliate system | 📋 Planned |
