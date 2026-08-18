"""
Integration tests — Phase 0.3: Configuration & Settings Framework.

Covers:
  1. Migration path A — brand-new database: migrations run from scratch,
     all tables and the category column are created by Alembic.

  2. Migration path B — unversioned Phase 0.2 database: a database that
     was created with create_all() (no alembic_version, no category column)
     is detected, stamped at revision 0001, and upgraded to HEAD so the
     category column is added.

  3. SettingsService full flow on a migrated database:
     seed_defaults(), get(), set(), delete(), exists(),
     reload_cache(), get_category().

Run:
    cd bot
    python -m pytest tests/test_settings_phase03.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Make sure bot/ is on sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Provide minimal required env vars for Settings to load.
os.environ.setdefault("BOT_TOKEN", "test_token_for_testing")
os.environ.setdefault("SESSION_SECRET", "test_session_secret_for_testing")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tmp_url(tmp_path: Path, name: str) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / name}"


async def _fresh_db(url: str):
    """Return an initialised DatabaseManager for *url* (runs full migrations)."""
    from database.connection import DatabaseManager

    DatabaseManager._instance = None  # reset singleton between tests
    db = DatabaseManager.initialise(url)
    await db.init()
    return db


# ---------------------------------------------------------------------------
# Migration path A — brand-new database
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_fresh_database_creates_category_column(tmp_path):
    """
    A brand-new SQLite database should have the category column in settings
    after DatabaseManager.init() runs all Alembic migrations from scratch.
    """
    from sqlalchemy import text

    db = await _fresh_db(_tmp_url(tmp_path, "fresh.db"))

    async with db.session() as session:
        result = await session.execute(text("PRAGMA table_info(settings)"))
        columns = {row[1] for row in result.fetchall()}  # row[1] = column name

    await db.close()

    assert "category" in columns, (
        "category column missing — migration 0002 did not run on a fresh database"
    )
    assert "key" in columns
    assert "value" in columns
    assert "type" in columns
    assert "is_public" in columns


@pytest.mark.asyncio
async def test_migration_alembic_version_at_head(tmp_path):
    """After init(), alembic_version must record current migration HEAD."""
    from sqlalchemy import text

    db = await _fresh_db(_tmp_url(tmp_path, "alembic_ver.db"))

    async with db.session() as session:
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        revision = result.scalar()

    await db.close()
    assert revision == "0040_phase81_admin_security", (
        f"Expected integrated HEAD 0040_phase81_admin_security, got {revision!r}"
    )


# ---------------------------------------------------------------------------
# Migration path B — unversioned Phase 0.2 database
# ---------------------------------------------------------------------------


async def _build_phase02_db(url: str) -> None:
    """
    Create a raw SQLite database that mimics Phase 0.2 state:
      • All 13 core tables created via create_all() (no Alembic).
      • settings table WITHOUT the category column (added in 0002).
      • users table WITHOUT first_name/last_name/status/last_active (added in 0003).
      • roles table WITHOUT permissions column (added in 0003).
      • No alembic_version table.

    Only the tables touched by migrations 0002 and 0003 need to be precise;
    other tables are created with minimal schemas sufficient for migration to run.
    """
    import aiosqlite

    db_path = url.replace("sqlite+aiosqlite:///", "")
    async with aiosqlite.connect(db_path) as conn:
        # settings — Phase 0.2 schema (no category column)
        await conn.execute("""
            CREATE TABLE settings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT    NOT NULL UNIQUE,
                value       TEXT    NOT NULL,
                type        TEXT    NOT NULL DEFAULT 'str',
                description TEXT,
                is_public   INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert a Phase 0.2 style row (no category).
        await conn.execute(
            "INSERT INTO settings (key, value, type, is_public) VALUES (?, ?, ?, ?)",
            ("legacy_key", "legacy_value", "str", 0),
        )

        # users — Phase 0.2 schema (no first_name / last_name / status / last_active)
        await conn.execute("""
            CREATE TABLE users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL UNIQUE,
                full_name   TEXT    NOT NULL,
                username    TEXT,
                role        TEXT    NOT NULL DEFAULT 'customer',
                language    TEXT    NOT NULL DEFAULT 'en',
                is_active   INTEGER NOT NULL DEFAULT 1,
                is_verified INTEGER NOT NULL DEFAULT 0,
                referred_by INTEGER,
                created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # roles — Phase 0.2 schema (no permissions column)
        await conn.execute("""
            CREATE TABLE roles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                label       TEXT    NOT NULL,
                description TEXT,
                is_system   INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.commit()


@pytest.mark.asyncio
async def test_migration_phase02_database_gets_category_column(tmp_path):
    """
    An existing Phase 0.2 database (create_all, no alembic_version, no category
    column) must be detected, stamped at 0001, and upgraded to HEAD so the
    category column is added without losing existing data.
    """
    from sqlalchemy import text

    url = _tmp_url(tmp_path, "phase02.db")

    # Build the Phase 0.2 database.
    await _build_phase02_db(url)

    # Run DatabaseManager.init() — should detect and upgrade.
    db = await _fresh_db(url)

    async with db.session() as session:
        # Verify category column was added.
        result = await session.execute(text("PRAGMA table_info(settings)"))
        columns = {row[1] for row in result.fetchall()}

        # Verify pre-existing data was preserved.
        result = await session.execute(text("SELECT value FROM settings WHERE key = 'legacy_key'"))
        legacy_value = result.scalar()

        # Verify alembic_version is at HEAD.
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        revision = result.scalar()

    await db.close()

    assert "category" in columns, (
        "category column not added to Phase 0.2 database by migration 0002"
    )
    assert legacy_value == "legacy_value", "Existing data was lost during migration"
    assert revision == "0040_phase81_admin_security", (
        f"Expected integrated HEAD 0040_phase81_admin_security, got {revision!r}"
    )


# ---------------------------------------------------------------------------
# SettingsService — full flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_service_seed_defaults(tmp_path):
    """seed_defaults() must insert all DEFAULT_SETTINGS and FEATURE_FLAG_DEFAULTS."""
    from app.services import SettingsService
    from config.defaults import DEFAULT_SETTINGS
    from config.feature_flags import FEATURE_FLAG_DEFAULTS

    db = await _fresh_db(_tmp_url(tmp_path, "seed.db"))
    svc = SettingsService(db)
    await svc.seed_defaults()

    # Every default setting key must be readable.
    for entry in DEFAULT_SETTINGS:
        val = await svc.get(entry["key"])
        assert val is not None, f"Default setting {entry['key']!r} not found after seed"

    # Every feature flag key must be readable.
    for key in FEATURE_FLAG_DEFAULTS:
        val = await svc.get(key)
        assert val is not None, f"Feature flag {key!r} not found after seed"

    await db.close()


@pytest.mark.asyncio
async def test_settings_service_seed_idempotent(tmp_path):
    """Calling seed_defaults() twice must not duplicate or overwrite rows."""
    from app.services import SettingsService

    db = await _fresh_db(_tmp_url(tmp_path, "seed2.db"))
    svc = SettingsService(db)

    await svc.seed_defaults()
    # Manually change a value.
    await svc.set("bot_name", "Custom Name", type_="str")

    # Second seed must not overwrite the manually changed value.
    await svc.seed_defaults()
    val = await svc.get("bot_name")
    assert val == "Custom Name", "seed_defaults() overwrote a manually set value on second call"

    await db.close()


@pytest.mark.asyncio
async def test_settings_service_get_set_delete(tmp_path):
    """get/set/delete cycle with typed values."""
    from app.services import SettingsService

    db = await _fresh_db(_tmp_url(tmp_path, "crud.db"))
    svc = SettingsService(db)
    await svc.seed_defaults()

    # Integer
    await svc.set("vpn_max_devices", 10, type_="int")
    assert await svc.get("vpn_max_devices") == 10

    # Bool
    await svc.set("feature_enable_maintenance", True, type_="bool")
    assert await svc.get("feature_enable_maintenance") is True

    # Float
    await svc.set("growth_referral_commission_pct", 15.5, type_="float")
    val = await svc.get("growth_referral_commission_pct")
    assert abs(val - 15.5) < 1e-6

    # String
    await svc.set("bot_name", "Test VPN", type_="str")
    assert await svc.get("bot_name") == "Test VPN"

    # Delete
    deleted = await svc.delete("bot_name")
    assert deleted is True
    assert await svc.get("bot_name", default="GONE") == "GONE"

    # Delete non-existent key
    deleted = await svc.delete("nonexistent_key_xyz")
    assert deleted is False

    await db.close()


@pytest.mark.asyncio
async def test_settings_service_exists(tmp_path):
    """exists() returns True for present keys, False for absent ones."""
    from app.services import SettingsService

    db = await _fresh_db(_tmp_url(tmp_path, "exists.db"))
    svc = SettingsService(db)
    await svc.seed_defaults()

    assert await svc.exists("bot_name") is True
    assert await svc.exists("completely_unknown_key_abc123") is False

    await db.close()


@pytest.mark.asyncio
async def test_settings_service_get_category(tmp_path):
    """get_category() returns only settings belonging to the requested category."""
    from app.services import SettingsService
    from config.defaults import SettingCategory, SettingKeys

    db = await _fresh_db(_tmp_url(tmp_path, "category.db"))
    svc = SettingsService(db)
    await svc.seed_defaults()

    vpn = await svc.get_category(SettingCategory.VPN)
    assert SettingKeys.MAX_DEVICES in vpn
    assert SettingKeys.SERVER_SELECTION in vpn
    # General keys must NOT appear under vpn.
    assert SettingKeys.BOT_NAME not in vpn

    general = await svc.get_category(SettingCategory.GENERAL)
    assert SettingKeys.BOT_NAME in general
    assert SettingKeys.CURRENCY in general

    features = await svc.get_category("features")
    from config.feature_flags import FeatureFlags

    assert FeatureFlags.ENABLE_MAINTENANCE in features
    assert FeatureFlags.ENABLE_WALLET in features

    await db.close()


@pytest.mark.asyncio
async def test_settings_service_reload_cache(tmp_path):
    """reload_cache() rebuilds the cache from DB, picking up external changes."""
    from app.services import SettingsService

    db = await _fresh_db(_tmp_url(tmp_path, "cache.db"))
    svc = SettingsService(db)
    await svc.seed_defaults()

    # Warm the cache.
    original = await svc.get("bot_name")

    # Write directly to DB bypassing the service cache.
    from sqlalchemy import text

    async with db.session() as session:
        await session.execute(
            text("UPDATE settings SET value = 'Direct DB Write' WHERE key = 'bot_name'")
        )

    # Cache still returns the stale value.
    assert await svc.get("bot_name") == original

    # After reload, the fresh value is returned.
    await svc.reload_cache()
    assert await svc.get("bot_name") == "Direct DB Write"

    await db.close()


@pytest.mark.asyncio
async def test_settings_service_validation_rejects_bad_types(tmp_path):
    """set() must raise ValueError when the value is incompatible with type_."""
    from app.services import SettingsService

    db = await _fresh_db(_tmp_url(tmp_path, "validate.db"))
    svc = SettingsService(db)
    await svc.seed_defaults()

    with pytest.raises(ValueError):
        await svc.set("vpn_max_devices", "not_an_int", type_="int")

    with pytest.raises(ValueError):
        await svc.set("growth_referral_commission_pct", "bad", type_="float")

    with pytest.raises(ValueError):
        await svc.set("bot_name", [1, 2, 3], type_="bool")

    await db.close()


@pytest.mark.asyncio
async def test_phase62_referral_policy_validation_rejects_unsafe_values(tmp_path):
    from app.services import SettingsService

    db = await _fresh_db(_tmp_url(tmp_path, "phase62_policy_validate.db"))
    svc = SettingsService(db)
    await svc.seed_defaults()
    with pytest.raises(ValueError):
        await svc.set("referral_reward_daily_limit", -1, type_="int")
    with pytest.raises(ValueError):
        await svc.set("referral_required_qualified_count", 0, type_="int")
    with pytest.raises(ValueError):
        await svc.set("referral_referrer_reward_type", "unknown", type_="str")
    with pytest.raises(ValueError):
        await svc.set("referral_reward_mode", "unbounded", type_="str")
    with pytest.raises(ValueError):
        await svc.set("referral_reward_wallet_currency", "MM", type_="str")
    await db.close()


@pytest.mark.asyncio
async def test_settings_service_validates_phase63_mission_policy(tmp_path):
    from app.services import SettingsService

    db = await _fresh_db(_tmp_url(tmp_path, "mission_policy.db"))
    svc = SettingsService(db)
    with pytest.raises(ValueError, match="non-negative"):
        await svc.set("mission_reward_daily_limit", -1, type_="int")
    with pytest.raises(ValueError, match="non-negative"):
        await svc.set("mission_menu_rate_limit_seconds", -1, type_="int")
    with pytest.raises(ValueError, match="Unsupported mission reward type"):
        await svc.set("mission_reward_type", "wallet", type_="str")
    await svc.set("mission_reward_type", "wallet_credit", type_="str")
    assert await svc.get("mission_reward_type") == "wallet_credit"
    await db.close()


@pytest.mark.asyncio
async def test_settings_service_validates_phase64_promo_policy(tmp_path):
    from app.services import SettingsService

    db = await _fresh_db(_tmp_url(tmp_path, "promo_policy.db"))
    svc = SettingsService(db)
    with pytest.raises(ValueError, match="non-negative"):
        await svc.set("promo_entry_rate_limit_seconds", -1, type_="int")
    with pytest.raises(ValueError, match="positive"):
        await svc.set("promo_invalid_attempt_limit", 0, type_="int")
    with pytest.raises(ValueError, match="cannot exceed"):
        await svc.set("promo_max_discount_percent", 101, type_="int")
    await svc.set("promo_max_discount_percent", 50, type_="int")
    assert await svc.get("promo_max_discount_percent") == 50
    await db.close()
