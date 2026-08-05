# Mental Outline VPN Platform

A scalable, commercial Telegram VPN bot powered by [Outline VPN](https://getoutline.org/). Built with Python 3.12, python-telegram-bot v21, SQLAlchemy 2 async, and APScheduler.

## How to Run

The bot runs via the **Mental VPN Bot** workflow (`cd bot && python main.py`).

It starts automatically. To restart it manually, use the Replit workflow panel.

## Required Secrets

Set these in the Replit **Secrets** panel (padlock icon):

| Secret | Description |
|--------|-------------|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `ADMIN_IDS` | Comma-separated Telegram user IDs with admin access (e.g. `123456789`) |
| `SESSION_SECRET` | Long random string for signing tokens (already set) |

## Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/mental_vpn.db` | DB connection URL |
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `DEFAULT_LANGUAGE` | `en` | `en` or `my` (Myanmar) |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

## Project Structure

All bot code lives in `bot/`. See `bot/README.md` for detailed architecture docs.

## Development Phases

| Phase | Scope | Status |
|-------|-------|--------|
| 0.1 | Foundation, architecture, scaffolding | ✅ Complete |
| 0.2 | Auth middleware, database migrations | ✅ Complete |
| 1 | User registration, language selection | 📋 Planned |
| 2 | Packages catalogue, admin UI | 📋 Planned |
| 3 | Wallet, payments | 📋 Planned |
| 4 | Outline VPN server & key management | 📋 Planned |
| 5 | Referral & affiliate system | 📋 Planned |

## User Preferences

- Keep the existing project structure — do not restructure or migrate to a different stack.
