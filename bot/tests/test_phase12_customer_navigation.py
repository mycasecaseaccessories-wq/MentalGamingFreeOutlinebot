"""Tests for Phase 1.2 customer navigation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.models.navigation import CustomerMenuItem
from app.services.customer_navigation_service import CustomerNavigationService


@pytest.mark.asyncio
async def test_open_main_persists_last_menu() -> None:
    preferences = AsyncMock()
    service = CustomerNavigationService(db=object(), preference_service=preferences)

    result = await service.open_main(1001)

    assert result == CustomerMenuItem.MAIN
    preferences.set_preference.assert_awaited_once_with(
        1001, "last_menu", "main"
    )


@pytest.mark.asyncio
async def test_open_destination_returns_metadata_and_persists() -> None:
    preferences = AsyncMock()
    service = CustomerNavigationService(db=object(), preference_service=preferences)

    result = await service.open_destination(1001, CustomerMenuItem.MY_KEYS)

    assert result.item == CustomerMenuItem.MY_KEYS
    assert result.title_key == "page.my_keys.title"
    preferences.set_preference.assert_awaited_once_with(
        1001, "last_menu", "my_keys"
    )


@pytest.mark.asyncio
async def test_unknown_destination_is_rejected() -> None:
    preferences = AsyncMock()
    service = CustomerNavigationService(db=object(), preference_service=preferences)

    with pytest.raises(ValueError):
        await service.open_destination(1001, "not-a-real-menu")


@pytest.mark.asyncio
async def test_get_last_menu_falls_back_to_main() -> None:
    preferences = AsyncMock()
    preferences.get_preference.return_value = "old_removed_menu"
    service = CustomerNavigationService(db=object(), preference_service=preferences)

    result = await service.get_last_menu(1001)

    assert result == CustomerMenuItem.MAIN


def test_all_required_customer_destinations_exist() -> None:
    service = CustomerNavigationService.__new__(CustomerNavigationService)
    items = {destination.item for destination in service.destinations()}

    assert items == {
        CustomerMenuItem.BUY_VPN,
        CustomerMenuItem.FREE_TRIAL,
        CustomerMenuItem.MY_KEYS,
        CustomerMenuItem.WALLET,
        CustomerMenuItem.PROFILE,
        CustomerMenuItem.SUPPORT,
        CustomerMenuItem.REFER_FRIENDS,
        CustomerMenuItem.MISSIONS,
        CustomerMenuItem.PROMO_CODE,
    }


def test_customer_keyboard_has_expected_layout() -> None:
    telegram = pytest.importorskip("telegram")
    from app.keyboards.main_menu import build_customer_main_menu

    markup = build_customer_main_menu("en")

    assert len(markup.keyboard) == 6
    assert [[button.text for button in row] for row in markup.keyboard] == [
        ["🛒 Buy VPN", "🎁 Free Trial"],
        ["🔑 My Keys", "💰 Wallet"],
        ["👤 Profile", "🎫 Support"],
        ["👥 Refer Friends"],
        ["🎯 Missions"],
        ["🎟 Promo Code"],
    ]
