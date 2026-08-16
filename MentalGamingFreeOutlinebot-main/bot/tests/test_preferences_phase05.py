"""
Phase 0.5 integration tests — User Preferences architecture.

Coverage:
  • UserPreference domain model: get(), to_dict(), PreferenceKey.is_valid().
  • PreferenceRepository: upsert, get_by_user_id, set_field, set_fields, reset,
    reset_field, get_users_with_notifications, get_users_for_broadcast.
  • PreferenceService: get_preference, set_preference, set_preferences,
    reset_preference, reset_all_preferences, get_all_preferences, get_or_create,
    in-memory cache invalidation.
  • Validation: unknown key, invalid language, invalid theme, bool coercion.
  • Migration 0004: user_preferences table and all columns present.
"""

from __future__ import annotations

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_url(tmp_path: Path, name: str) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / name}"


async def _fresh_db(url: str):
    from database.connection import DatabaseManager
    dm = DatabaseManager.initialise(url)
    await dm.init()
    return dm


# ---------------------------------------------------------------------------
# UserPreference domain model
# ---------------------------------------------------------------------------

def test_preference_key_is_valid():
    from app.models.user_preference import PreferenceKey
    assert PreferenceKey.is_valid("language") is True
    assert PreferenceKey.is_valid("timezone") is True
    assert PreferenceKey.is_valid("nonexistent_key") is False


def test_user_preference_defaults():
    from app.models.user_preference import UserPreference
    pref = UserPreference(user_id=1)
    assert pref.language == "en"
    assert pref.timezone == "Asia/Rangoon"
    assert pref.preferred_currency == "MMK"
    assert pref.notification_enabled is True
    assert pref.broadcast_enabled is True
    assert pref.privacy_mode is False
    assert pref.theme == "default"
    assert pref.last_menu is None
    assert pref.preferred_server_country is None


def test_user_preference_get():
    from app.models.user_preference import UserPreference, PreferenceKey
    pref = UserPreference(user_id=2, language="my", theme="dark")
    assert pref.get(PreferenceKey.LANGUAGE) == "my"
    assert pref.get(PreferenceKey.THEME) == "dark"


def test_user_preference_get_invalid_key():
    from app.models.user_preference import UserPreference
    pref = UserPreference(user_id=3)
    with pytest.raises(AttributeError):
        pref.get("totally_unknown_key")


def test_user_preference_to_dict():
    from app.models.user_preference import UserPreference, PreferenceKey
    pref = UserPreference(user_id=4, language="my")
    d = pref.to_dict()
    assert isinstance(d, dict)
    assert d[PreferenceKey.LANGUAGE] == "my"
    assert PreferenceKey.TIMEZONE in d
    # All known keys present.
    for key in PreferenceKey.ALL:
        assert key in d


# ---------------------------------------------------------------------------
# PreferenceRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repo_upsert_creates_new(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_new.db"))
    async with db.session() as session:
        from database.repositories.preference_repository import PreferenceRepository
        repo = PreferenceRepository(session)
        row, created = await repo.upsert(500001)
    await db.close()
    assert created is True
    assert row.user_id == 500001
    assert row.language == "en"
    assert row.notification_enabled is True


@pytest.mark.asyncio
async def test_repo_upsert_existing(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_existing.db"))
    async with db.session() as session:
        from database.repositories.preference_repository import PreferenceRepository
        repo = PreferenceRepository(session)
        await repo.upsert(500002)

    async with db.session() as session:
        from database.repositories.preference_repository import PreferenceRepository
        repo = PreferenceRepository(session)
        row, created = await repo.upsert(500002)

    await db.close()
    assert created is False
    assert row.user_id == 500002


@pytest.mark.asyncio
async def test_repo_set_field(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_set.db"))
    async with db.session() as session:
        from database.repositories.preference_repository import PreferenceRepository
        repo = PreferenceRepository(session)
        await repo.upsert(500003)
        row = await repo.set_field(500003, "language", "my")
    await db.close()
    assert row.language == "my"


@pytest.mark.asyncio
async def test_repo_set_fields(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_set_fields.db"))
    async with db.session() as session:
        from database.repositories.preference_repository import PreferenceRepository
        repo = PreferenceRepository(session)
        row = await repo.set_fields(500004, {
            "language": "my",
            "theme": "dark",
            "notification_enabled": False,
        })
    await db.close()
    assert row.language == "my"
    assert row.theme == "dark"
    assert row.notification_enabled is False


@pytest.mark.asyncio
async def test_repo_set_field_invalid_column(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_bad_col.db"))
    async with db.session() as session:
        from database.repositories.preference_repository import PreferenceRepository
        repo = PreferenceRepository(session)
        with pytest.raises(AttributeError):
            await repo.set_field(500005, "nonexistent_column", "value")
    await db.close()


@pytest.mark.asyncio
async def test_repo_reset(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_reset.db"))
    async with db.session() as session:
        from database.repositories.preference_repository import PreferenceRepository
        repo = PreferenceRepository(session)
        await repo.set_field(500006, "language", "my")
        row = await repo.reset(500006)
    await db.close()
    # After reset, all values should be defaults.
    assert row.language == "en"
    assert row.theme == "default"


@pytest.mark.asyncio
async def test_repo_notification_query(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_notif.db"))
    async with db.session() as session:
        from database.repositories.preference_repository import PreferenceRepository
        repo = PreferenceRepository(session)
        await repo.upsert(500010)  # notifications ON by default
        await repo.set_field(500011, "notification_enabled", False)  # creates + disables

        notif_rows = await repo.get_users_with_notifications()
        broadcast_rows = await repo.get_users_for_broadcast()

    await db.close()
    notif_ids = {r.user_id for r in notif_rows}
    assert 500010 in notif_ids
    assert 500011 not in notif_ids
    broadcast_ids = {r.user_id for r in broadcast_rows}
    assert 500010 in broadcast_ids


# ---------------------------------------------------------------------------
# PreferenceService
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_service_get_preference_default(tmp_path):
    """get_preference() returns default for a fresh user (no prior row)."""
    db = await _fresh_db(_tmp_url(tmp_path, "svc_get.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey

    svc = PreferenceService(db)
    lang = await svc.get_preference(600001, PreferenceKey.LANGUAGE)
    tz   = await svc.get_preference(600001, PreferenceKey.TIMEZONE)
    await db.close()
    assert lang == "en"
    assert tz == "Asia/Rangoon"


@pytest.mark.asyncio
async def test_service_set_preference(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_set.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey

    svc = PreferenceService(db)
    pref = await svc.set_preference(600002, PreferenceKey.LANGUAGE, "my")
    assert pref.language == "my"
    # Cache must be updated.
    cached = await svc.get_preference(600002, PreferenceKey.LANGUAGE)
    assert cached == "my"
    await db.close()


@pytest.mark.asyncio
async def test_service_set_preferences_bulk(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_bulk.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey

    svc = PreferenceService(db)
    pref = await svc.set_preferences(600003, {
        PreferenceKey.LANGUAGE:            "my",
        PreferenceKey.THEME:               "dark",
        PreferenceKey.NOTIFICATION_ENABLED: False,
        PreferenceKey.PREFERRED_CURRENCY:  "USD",
    })
    await db.close()
    assert pref.language == "my"
    assert pref.theme == "dark"
    assert pref.notification_enabled is False
    assert pref.preferred_currency == "USD"


@pytest.mark.asyncio
async def test_service_reset_preference(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_reset_one.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey

    svc = PreferenceService(db)
    await svc.set_preference(600004, PreferenceKey.LANGUAGE, "my")
    pref = await svc.reset_preference(600004, PreferenceKey.LANGUAGE)
    await db.close()
    assert pref.language == "en"


@pytest.mark.asyncio
async def test_service_reset_all_preferences(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_reset_all.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey

    svc = PreferenceService(db)
    await svc.set_preferences(600005, {
        PreferenceKey.LANGUAGE: "my",
        PreferenceKey.THEME:    "dark",
        PreferenceKey.PRIVACY_MODE: True,
    })
    pref = await svc.reset_all_preferences(600005)
    await db.close()
    assert pref.language == "en"
    assert pref.theme == "default"
    assert pref.privacy_mode is False


@pytest.mark.asyncio
async def test_service_get_all_preferences(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_all.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey, UserPreference

    svc = PreferenceService(db)
    pref = await svc.get_all_preferences(600006)
    await db.close()
    assert isinstance(pref, UserPreference)
    assert pref.user_id == 600006
    assert pref.language == "en"


@pytest.mark.asyncio
async def test_service_in_memory_cache(tmp_path):
    """Second get_preference() call uses in-memory cache (no extra DB hit)."""
    db = await _fresh_db(_tmp_url(tmp_path, "svc_cache.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey

    svc = PreferenceService(db)
    await svc.get_preference(600007, PreferenceKey.LANGUAGE)
    # Populate cache.
    assert 600007 in svc._cache
    # Invalidate.
    svc.invalidate_cache(600007)
    assert 600007 not in svc._cache
    await db.close()


@pytest.mark.asyncio
async def test_service_get_or_create(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_get_or_create.db"))
    from app.services import PreferenceService

    svc = PreferenceService(db)
    pref, created = await svc.get_or_create(600008)
    assert created is True

    pref2, created2 = await svc.get_or_create(600008)
    assert created2 is False
    await db.close()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_service_invalid_key_raises(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_badkey.db"))
    from app.services import PreferenceService
    svc = PreferenceService(db)
    with pytest.raises(ValueError, match="Unknown preference key"):
        await svc.get_preference(700001, "bad_key")
    with pytest.raises(ValueError, match="Unknown preference key"):
        await svc.set_preference(700001, "bad_key", "value")
    await db.close()


@pytest.mark.asyncio
async def test_service_invalid_language_raises(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_badlang.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey
    svc = PreferenceService(db)
    with pytest.raises(ValueError, match="Unsupported language"):
        await svc.set_preference(700002, PreferenceKey.LANGUAGE, "zz")
    await db.close()


@pytest.mark.asyncio
async def test_service_invalid_theme_raises(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_badtheme.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey
    svc = PreferenceService(db)
    with pytest.raises(ValueError, match="Unsupported theme"):
        await svc.set_preference(700003, PreferenceKey.THEME, "neon_rainbow")
    await db.close()


@pytest.mark.asyncio
async def test_service_bool_coercion(tmp_path):
    """String 'true'/'false' should be coerced to bool for boolean preferences."""
    db = await _fresh_db(_tmp_url(tmp_path, "svc_bool.db"))
    from app.services import PreferenceService
    from app.models.user_preference import PreferenceKey

    svc = PreferenceService(db)
    pref = await svc.set_preference(700004, PreferenceKey.NOTIFICATION_ENABLED, "false")
    assert pref.notification_enabled is False

    pref = await svc.set_preference(700004, PreferenceKey.BROADCAST_ENABLED, "true")
    assert pref.broadcast_enabled is True
    await db.close()


# ---------------------------------------------------------------------------
# Migration 0004 schema check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_migration_0004_table_exists(tmp_path):
    """After migration 0004, user_preferences table must exist."""
    from sqlalchemy import text
    db = await _fresh_db(_tmp_url(tmp_path, "schema_pref.db"))
    async with db.session() as session:
        result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        )
        table_name = result.scalar()
    await db.close()
    assert table_name == "user_preferences"


@pytest.mark.asyncio
async def test_migration_0004_columns(tmp_path):
    """user_preferences must have all Phase 0.5 columns."""
    from sqlalchemy import text
    db = await _fresh_db(_tmp_url(tmp_path, "schema_pref_cols.db"))
    async with db.session() as session:
        result = await session.execute(text("PRAGMA table_info(user_preferences)"))
        columns = {row[1] for row in result.fetchall()}
    await db.close()

    expected = {
        "id", "user_id", "language", "timezone", "preferred_currency",
        "notification_enabled", "broadcast_enabled", "privacy_mode",
        "theme", "last_menu", "preferred_server_country",
        "created_at", "updated_at",
    }
    for col in expected:
        assert col in columns, f"Column {col!r} missing from user_preferences"


@pytest.mark.asyncio
async def test_migration_head_is_current(tmp_path):
    """After init(), alembic_version must record the current migration HEAD."""
    from sqlalchemy import text
    db = await _fresh_db(_tmp_url(tmp_path, "head_check.db"))
    async with db.session() as session:
        result = await session.execute(
            text("SELECT version_num FROM alembic_version")
        )
        revision = result.scalar()
    await db.close()
    assert revision == "0008", f"Expected HEAD 0008, got {revision!r}"
