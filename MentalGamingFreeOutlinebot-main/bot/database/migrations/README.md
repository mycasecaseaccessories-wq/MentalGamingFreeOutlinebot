# Database Migrations

This directory contains [Alembic](https://alembic.sqlalchemy.org/) migration scripts.

Alembic provides schema versioning and safe incremental migrations for both
SQLite (development) and PostgreSQL (production).

---

## Initialise Alembic (one-time setup, Phase 0.3)

```bash
cd bot
alembic init database/migrations
```

Then edit `alembic.ini` and `database/migrations/env.py` to use the async
SQLAlchemy engine defined in `database/connection.py`.

---

## Create a new migration

After changing an ORM model in `database/models/`:

```bash
alembic revision --autogenerate -m "add_subscription_status_to_orders"
```

Review the generated script in `database/migrations/versions/` before applying.

---

## Apply migrations

```bash
# Upgrade to latest
alembic upgrade head

# Downgrade one step
alembic downgrade -1

# Show current revision
alembic current
```

---

## Phase 0.2 note

In Phase 0.2 the database schema is created with `create_all()` at startup
(see `database/connection.py`).  This is safe for development but not for
production where migrations must be applied incrementally.

Alembic will be fully wired in Phase 0.3:
- `alembic.ini` added to `bot/`
- `database/migrations/env.py` configured for async engine
- Initial migration generated from the Phase 0.2 schema baseline
