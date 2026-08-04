"""
Phase 0.4 integration tests — Role System, Authentication & Multi-Language.

Coverage:
  • UserRepository: upsert, get_by_telegram_id, update_last_active,
    update_status, update_language, update_role.
  • UserService:    register_user (new + returning), get_profile,
                    change_language, change_status, ban/unban.
  • LanguageService: translate, load_language, set_language, get_language,
                     cache_language, get_cached_language.
  • User domain model: properties (can_use_bot, is_banned, short_name, …).
  • Translator: English / Myanmar key resolution, fallback, missing key.
  • Migration 0003: users table has new columns; roles table has permissions.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_url(tmp_path: Path, name: str) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / name}"


async def _fresh_db(url: str):
    """Return an initialised DatabaseManager using the given URL."""
    from database.connection import DatabaseManager

    dm = DatabaseManager.initialise(url)
    await dm.init()
    return dm


# ---------------------------------------------------------------------------
# User domain model
# ---------------------------------------------------------------------------

def test_user_domain_properties():
    """User domain properties are computed correctly from status/role."""
    from app.models.user import User
    from app.models.enums import UserRole, UserStatus, Language

    active_user = User(telegram_id=1, full_name="Alice", first_name="Alice")
    assert active_user.can_use_bot is True
    assert active_user.is_banned is False
    assert active_user.is_suspended is False
    assert active_user.short_name == "Alice"
    assert active_user.is_admin is False
    assert active_user.is_customer is True

    banned = User(
        telegram_id=2, full_name="Bob", status=UserStatus.BANNED, role=UserRole.CUSTOMER
    )
    assert banned.can_use_bot is False
    assert banned.is_banned is True
    assert banned.is_suspended is False

    suspended = User(
        telegram_id=3, full_name="Charlie", status=UserStatus.SUSPENDED
    )
    assert suspended.can_use_bot is False
    assert suspended.is_banned is False
    assert suspended.is_suspended is True

    admin = User(telegram_id=4, full_name="Admin", role=UserRole.ADMIN)
    assert admin.is_admin is True
    assert admin.is_customer is False
    assert admin.can_use_bot is True


def test_user_short_name_fallback():
    """short_name falls back to the first token of full_name."""
    from app.models.user import User

    u = User(telegram_id=5, full_name="Dave Smith", first_name=None)
    assert u.short_name == "Dave"

    u2 = User(telegram_id=6, full_name="Eve", first_name="Eve")
    assert u2.short_name == "Eve"


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

def test_translator_english_key():
    from locales.translator import t

    text = t("welcome.greeting", language="en", name="Alice")
    assert "Alice" in text
    assert "Welcome" in text or "welcome" in text.lower()


def test_translator_myanmar_key():
    from locales.translator import t

    text = t("auth.banned", language="my")
    assert text  # Non-empty
    assert text != "auth.banned"  # Key was resolved


def test_translator_fallback_to_english():
    """Keys present in English but missing in 'my' should fall back to English."""
    from locales.translator import t, _get_registry

    registry = _get_registry()
    # Manually remove a key from 'my' to test fallback.
    my_translations = registry.get("my", {})
    saved = my_translations.pop("welcome.greeting", None)

    try:
        text = t("welcome.greeting", language="my", name="Fallback")
        assert "Fallback" in text
    finally:
        if saved is not None:
            my_translations["welcome.greeting"] = saved


def test_translator_missing_key_returns_key():
    """A completely missing key returns the key string (never raises)."""
    from locales.translator import t
    import logging

    result = t("nonexistent.key.xyz", language="en")
    assert result == "nonexistent.key.xyz"


def test_translator_class():
    """Translator class works the same as module-level t()."""
    from locales.translator import Translator

    tr = Translator("en")
    result = tr.get("common.done")
    assert "Done" in result or result != "common.done"


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_repository_upsert_new(tmp_path):
    """upsert() creates a new user row on first call."""
    db = await _fresh_db(_tmp_url(tmp_path, "repo_new.db"))

    async with db.session() as session:
        from database.repositories import UserRepository

        repo = UserRepository(session)
        row, created = await repo.upsert(
            telegram_id=100001,
            full_name="Test User",
            username="testuser",
            first_name="Test",
            last_name="User",
        )

    await db.close()

    assert created is True
    assert row.telegram_id == 100001
    assert row.first_name == "Test"
    assert row.last_name == "User"
    assert row.status == "active"


@pytest.mark.asyncio
async def test_user_repository_upsert_existing(tmp_path):
    """upsert() returns created=False and refreshes mutable fields on repeat call."""
    db = await _fresh_db(_tmp_url(tmp_path, "repo_existing.db"))

    async with db.session() as session:
        from database.repositories import UserRepository

        repo = UserRepository(session)
        await repo.upsert(telegram_id=100002, full_name="Old Name")

    async with db.session() as session:
        from database.repositories import UserRepository

        repo = UserRepository(session)
        row, created = await repo.upsert(
            telegram_id=100002, full_name="New Name"
        )

    await db.close()
    assert created is False
    assert row.full_name == "New Name"


@pytest.mark.asyncio
async def test_user_repository_update_language(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_lang.db"))

    async with db.session() as session:
        from database.repositories import UserRepository

        repo = UserRepository(session)
        await repo.upsert(telegram_id=100003, full_name="Lang User")
        updated = await repo.update_language(100003, "my")

    await db.close()
    assert updated is not None
    assert updated.language == "my"


@pytest.mark.asyncio
async def test_user_repository_update_status(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "repo_status.db"))

    async with db.session() as session:
        from database.repositories import UserRepository

        repo = UserRepository(session)
        await repo.upsert(telegram_id=100004, full_name="Status User")
        updated = await repo.update_status(100004, "banned")

    await db.close()
    assert updated is not None
    assert updated.status == "banned"
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_user_repository_update_last_active(tmp_path):
    """update_last_active() runs without error and stamps the row."""
    from sqlalchemy import text

    db = await _fresh_db(_tmp_url(tmp_path, "repo_active.db"))

    async with db.session() as session:
        from database.repositories import UserRepository

        repo = UserRepository(session)
        await repo.upsert(telegram_id=100005, full_name="Active User")
        await repo.update_last_active(100005)
        # Verify the value was set.
        row = await repo.get_by_telegram_id(100005)

    await db.close()
    assert row.last_active is not None


# ---------------------------------------------------------------------------
# UserService
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_service_register_new(tmp_path):
    """register_user() creates a new profile and returns created=True."""
    db = await _fresh_db(_tmp_url(tmp_path, "svc_new.db"))
    from app.services import UserService

    svc = UserService(db)
    user, created = await svc.register_user(
        telegram_id=200001,
        full_name="Service User",
        username="svcuser",
        first_name="Service",
        last_name="User",
    )
    await db.close()

    assert created is True
    assert user.telegram_id == 200001
    assert user.first_name == "Service"
    assert user.can_use_bot is True


@pytest.mark.asyncio
async def test_user_service_register_returning(tmp_path):
    """register_user() returns created=False on second call for same user."""
    db = await _fresh_db(_tmp_url(tmp_path, "svc_return.db"))
    from app.services import UserService

    svc = UserService(db)
    await svc.register_user(telegram_id=200002, full_name="Returning User")
    _, created = await svc.register_user(telegram_id=200002, full_name="Returning User")
    await db.close()
    assert created is False


@pytest.mark.asyncio
async def test_user_service_change_language_valid(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_lang.db"))
    from app.services import UserService

    svc = UserService(db)
    await svc.register_user(telegram_id=200003, full_name="Lang User")
    user = await svc.change_language(200003, "my")
    await db.close()

    assert user is not None
    from app.models.enums import Language
    assert user.language == Language.MYANMAR


@pytest.mark.asyncio
async def test_user_service_change_language_invalid(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_lang_bad.db"))
    from app.services import UserService

    svc = UserService(db)
    await svc.register_user(telegram_id=200004, full_name="Lang Bad")
    await db.close()

    with pytest.raises(ValueError, match="Unsupported language"):
        await svc.change_language(200004, "zz")


@pytest.mark.asyncio
async def test_user_service_ban_unban(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "svc_ban.db"))
    from app.services import UserService
    from app.models.enums import UserStatus

    svc = UserService(db)
    await svc.register_user(telegram_id=200005, full_name="Ban Target")
    await svc.ban(200005)

    user = await svc.get_profile(200005)
    assert user.is_banned is True
    assert user.can_use_bot is False

    await svc.unban(200005)
    user = await svc.get_profile(200005)
    assert user.status == UserStatus.ACTIVE
    assert user.can_use_bot is True

    await db.close()


# ---------------------------------------------------------------------------
# LanguageService
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_language_service_translate(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "ls_translate.db"))
    from app.services import LanguageService

    svc = LanguageService(db)
    text = svc.translate("common.done", "en")
    assert text != "common.done"  # Key was resolved.

    my_text = svc.translate("common.cancel", "my")
    assert my_text != "common.cancel"
    await db.close()


@pytest.mark.asyncio
async def test_language_service_cache(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "ls_cache.db"))
    from app.services import LanguageService

    svc = LanguageService(db)
    svc.cache_language(300001, "my")
    assert svc.get_cached_language(300001) == "my"
    assert svc.get_cached_language(999999) == "en"  # Default.
    await db.close()


@pytest.mark.asyncio
async def test_language_service_set_and_get(tmp_path):
    db = await _fresh_db(_tmp_url(tmp_path, "ls_setget.db"))
    from app.services import LanguageService, UserService

    user_svc = UserService(db)
    lang_svc = LanguageService(db)

    await user_svc.register_user(telegram_id=300002, full_name="Lang Persist")
    await lang_svc.set_language(300002, "my")
    lang = await lang_svc.get_language(300002)
    await db.close()

    assert lang == "my"


# ---------------------------------------------------------------------------
# Migration 0003 schema check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_migration_0003_users_columns(tmp_path):
    """After migration 0003, users must have first_name, last_name, status, last_active."""
    from sqlalchemy import text

    db = await _fresh_db(_tmp_url(tmp_path, "schema_users.db"))

    async with db.session() as session:
        result = await session.execute(text("PRAGMA table_info(users)"))
        columns = {row[1] for row in result.fetchall()}

    await db.close()

    for col in ("first_name", "last_name", "status", "last_active"):
        assert col in columns, f"Column {col!r} missing from users table after migration 0003"


@pytest.mark.asyncio
async def test_migration_0003_roles_columns(tmp_path):
    """After migration 0003, roles must have a permissions column."""
    from sqlalchemy import text

    db = await _fresh_db(_tmp_url(tmp_path, "schema_roles.db"))

    async with db.session() as session:
        result = await session.execute(text("PRAGMA table_info(roles)"))
        columns = {row[1] for row in result.fetchall()}

    await db.close()
    assert "permissions" in columns, "permissions column missing from roles table"
