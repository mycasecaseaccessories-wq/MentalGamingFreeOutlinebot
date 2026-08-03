# Mental Outline VPN Platform

A scalable, commercial Telegram VPN platform powered by [Outline VPN](https://getoutline.org/).

> **Phase 0.1 — Foundation & Architecture**
> Business features are not yet implemented. This release establishes the project structure, configuration, database scaffolding, and service/handler stubs ready for Phase 1.

---

## Tech Stack

| Layer        | Technology                        |
|--------------|-----------------------------------|
| Language     | Python 3.12+                      |
| Bot Framework| python-telegram-bot v21           |
| Database     | SQLite (dev) / PostgreSQL (prod)  |
| ORM          | SQLAlchemy 2 async                |
| Validation   | Pydantic v2                       |
| Scheduler    | APScheduler 3                     |
| VPN          | Outline VPN (Phase 4)             |

---

## Project Structure

```
bot/
├── main.py                 # Application entry point
├── requirements.txt
├── .env.example            # Environment variable template
│
├── config/
│   └── settings.py         # Centralised config (reads env vars)
│
├── app/
│   ├── handlers/           # Telegram update handlers
│   │   ├── base.py         # Shared decorators (admin_only, log_handler)
│   │   ├── start.py        # /start, /help
│   │   ├── admin.py        # /admin
│   │   └── error.py        # Global error handler
│   │
│   ├── services/           # Business logic layer
│   │   ├── base.py
│   │   ├── user_service.py
│   │   ├── package_service.py
│   │   ├── wallet_service.py
│   │   ├── server_service.py
│   │   ├── vpn_service.py
│   │   ├── growth_service.py
│   │   └── notification_service.py
│   │
│   ├── repositories/       # Data access layer (repository pattern)
│   │   ├── base.py
│   │   └── user_repository.py
│   │
│   ├── models/             # Domain models and enums
│   │   ├── enums.py        # UserRole, Language
│   │   └── user.py
│   │
│   ├── keyboards/          # Telegram keyboard builders
│   │   └── main_menu.py
│   │
│   ├── middlewares/        # Cross-cutting concerns
│   │   ├── auth.py
│   │   └── logging.py
│   │
│   ├── utils/
│   │   ├── logger.py       # Logging setup (rotating file + console)
│   │   └── helpers.py      # escape_html, truncate, format_bytes
│   │
│   └── scheduler/
│       └── base.py         # APScheduler wrapper
│
├── database/
│   ├── connection.py       # Async SQLAlchemy engine + session factory
│   └── base.py             # Declarative ORM base class
│
├── locales/
│   ├── translator.py       # t() function, Translator class, fallback logic
│   ├── en.py               # English translations
│   └── my.py               # Myanmar translations
│
└── logs/                   # Auto-created; gitignored
```

---

## Quick Start

### 1. Clone & install

```bash
cd bot
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set BOT_TOKEN and ADMIN_IDS at minimum
```

On Replit: add `BOT_TOKEN` and `ADMIN_IDS` in the **Secrets** panel.

### 3. Run

```bash
python main.py
```

---

## Environment Variables

| Variable          | Required | Default                            | Description                            |
|-------------------|----------|------------------------------------|----------------------------------------|
| `BOT_TOKEN`       | ✅        | —                                  | Telegram bot token from @BotFather     |
| `ADMIN_IDS`       | ✅        | —                                  | Comma-separated Telegram user IDs      |
| `DATABASE_URL`    | ❌        | `sqlite+aiosqlite:///./data/…`     | SQLAlchemy async connection URL        |
| `ENVIRONMENT`     | ❌        | `development`                      | `development` / `staging` / `production` |
| `DEFAULT_LANGUAGE`| ❌        | `en`                               | Default UI language (`en` / `my`)      |
| `LOG_LEVEL`       | ❌        | `INFO`                             | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## Development Phases

| Phase | Scope                                      | Status      |
|-------|--------------------------------------------|-------------|
| 0.1   | Foundation, architecture, scaffolding      | ✅ Complete  |
| 0.2   | Auth middleware, database migrations       | 🔜 Next      |
| 1     | User registration, language selection      | 📋 Planned   |
| 2     | Packages catalogue, admin UI               | 📋 Planned   |
| 3     | Wallet, payments                           | 📋 Planned   |
| 4     | Outline VPN server & key management        | 📋 Planned   |
| 5     | Referral & affiliate system                | 📋 Planned   |

---

## Architecture Principles

- **SOLID** — each class has a single responsibility; services depend on repository abstractions.
- **Repository pattern** — all SQL lives in `repositories/`; services never write queries.
- **Async throughout** — every I/O operation (DB, HTTP, Telegram) is async/await.
- **Config by environment** — no hardcoded secrets; all values come from env vars.
- **Fail loudly** — missing required env vars raise `ValueError` at startup, not at runtime.
