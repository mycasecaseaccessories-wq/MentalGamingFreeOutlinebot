from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.customer_entry import EntryRoute
from app.models.enums import Language, UserRole, UserStatus
from app.models.user import User
from app.services.customer_entry_service import CustomerEntryService


class FakePreferenceService:
    def __init__(self, *, selected: bool, language: str = "en") -> None:
        self.pref = SimpleNamespace(language_selected=selected, language=language)
        self.set_preferences = AsyncMock(return_value=self.pref)

    async def get_or_create(self, user_id: int):
        return self.pref, False


class FakeUserService:
    def __init__(self, user: User) -> None:
        self.user = user
        self.change_role = AsyncMock(side_effect=self._change_role)
        self.change_language = AsyncMock(side_effect=self._change_language)

    async def _change_role(self, telegram_id: int, role: str):
        self.user = replace(self.user, role=UserRole(role))
        return self.user

    async def _change_language(self, telegram_id: int, language: str):
        self.user = replace(self.user, language=Language(language))
        return self.user


def make_user(
    *,
    telegram_id: int = 123,
    role: UserRole = UserRole.CUSTOMER,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    return User(
        telegram_id=telegram_id,
        full_name="Test User",
        first_name="Test",
        role=role,
        status=status,
    )


@pytest.mark.asyncio
async def test_first_time_customer_requires_language_selection():
    user = make_user()
    prefs = FakePreferenceService(selected=False)
    service = CustomerEntryService(
        db=object(),
        user_service=FakeUserService(user),
        preference_service=prefs,
    )
    decision = await service.resolve(
        user=user,
        is_new_user=True,
        admin_ids=[],
    )
    assert decision.route == EntryRoute.LANGUAGE_SELECTION


@pytest.mark.asyncio
async def test_returning_customer_routes_without_key_check():
    user = make_user()
    prefs = FakePreferenceService(selected=True, language="my")
    service = CustomerEntryService(
        db=object(),
        user_service=FakeUserService(user),
        preference_service=prefs,
    )
    decision = await service.resolve(
        user=user,
        is_new_user=False,
        admin_ids=[],
    )
    assert decision.route == EntryRoute.CUSTOMER
    assert decision.language == "my"


@pytest.mark.asyncio
async def test_admin_id_is_promoted_and_routed_to_admin():
    user = make_user(telegram_id=999)
    prefs = FakePreferenceService(selected=True)
    users = FakeUserService(user)
    service = CustomerEntryService(
        db=object(),
        user_service=users,
        preference_service=prefs,
    )
    decision = await service.resolve(
        user=user,
        is_new_user=False,
        admin_ids=[999],
    )
    assert decision.route == EntryRoute.ADMIN
    users.change_role.assert_awaited_once_with(999, "admin")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_key"),
    [
        (UserStatus.BANNED, "auth.banned"),
        (UserStatus.SUSPENDED, "auth.suspended"),
    ],
)
async def test_restricted_user_is_not_routed_to_customer(status, expected_key):
    user = make_user(status=status)
    service = CustomerEntryService(
        db=object(),
        user_service=FakeUserService(user),
        preference_service=FakePreferenceService(selected=True),
    )
    decision = await service.resolve(
        user=user,
        is_new_user=False,
        admin_ids=[],
    )
    assert decision.route == EntryRoute.ACCESS_RESTRICTED
    assert decision.restriction_key == expected_key


@pytest.mark.asyncio
async def test_language_selection_continues_to_customer():
    user = make_user()
    prefs = FakePreferenceService(selected=False)
    users = FakeUserService(user)
    service = CustomerEntryService(
        db=object(),
        user_service=users,
        preference_service=prefs,
    )
    decision = await service.select_language(user, "my")
    assert decision.route == EntryRoute.CUSTOMER
    assert decision.language == "my"
    prefs.set_preferences.assert_awaited_once()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ref_ABC-123", "ref_ABC-123"),
        (" campaign ", "campaign"),
        ("bad token!", None),
        ("x" * 65, None),
        ("", None),
        (None, None),
    ],
)
def test_start_parameter_sanitization(raw, expected):
    assert CustomerEntryService.sanitize_start_parameter(raw) == expected
