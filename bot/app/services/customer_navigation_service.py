"""Customer navigation service for Phase 1.2.

This service owns navigation decisions and preference state. It deliberately
contains no Telegram-specific objects and no business logic for packages,
wallets, VPN keys, free trials, or payments.
"""

from __future__ import annotations

from app.models.navigation import CustomerMenuItem, NavigationDestination
from app.models.user_preference import PreferenceKey
from app.services.base import BaseService
from app.services.preference_service import PreferenceService


_DESTINATIONS: dict[CustomerMenuItem, NavigationDestination] = {
    CustomerMenuItem.BUY_VPN: NavigationDestination(
        CustomerMenuItem.BUY_VPN,
        "page.buy_vpn.title",
        "page.buy_vpn.body",
    ),
    CustomerMenuItem.FREE_TRIAL: NavigationDestination(
        CustomerMenuItem.FREE_TRIAL,
        "page.free_trial.title",
        "page.free_trial.body",
    ),
    CustomerMenuItem.MY_KEYS: NavigationDestination(
        CustomerMenuItem.MY_KEYS,
        "page.my_keys.title",
        "page.my_keys.body",
    ),
    CustomerMenuItem.WALLET: NavigationDestination(
        CustomerMenuItem.WALLET,
        "page.wallet.title",
        "page.wallet.body",
    ),
    CustomerMenuItem.ORDERS: NavigationDestination(
        CustomerMenuItem.ORDERS,
        "page.orders.title",
        "page.orders.body",
        implemented=True,
    ),
    CustomerMenuItem.PAYMENTS: NavigationDestination(
        CustomerMenuItem.PAYMENTS,
        "page.payments.title",
        "page.payments.body",
        implemented=True,
    ),
    CustomerMenuItem.PROFILE: NavigationDestination(
        CustomerMenuItem.PROFILE,
        "page.profile.title",
        "page.profile.body",
    ),
    CustomerMenuItem.SUPPORT: NavigationDestination(
        CustomerMenuItem.SUPPORT,
        "page.support.title",
        "page.support.body",
    ),
    CustomerMenuItem.REFER_FRIENDS: NavigationDestination(
        CustomerMenuItem.REFER_FRIENDS,
        "referral.invite_title",
        "referral.invite_body",
        implemented=True,
    ),
    CustomerMenuItem.MISSIONS: NavigationDestination(
        CustomerMenuItem.MISSIONS,
        "missions.title",
        "missions.body",
        implemented=True,
    ),
}


class CustomerNavigationService(BaseService):
    """Resolve customer destinations and persist navigation state."""

    def __init__(
        self,
        db=None,
        preference_service: PreferenceService | None = None,
    ) -> None:
        super().__init__(db)
        self.preference_service = preference_service or PreferenceService(db)

    async def open_main(self, user_id: int) -> CustomerMenuItem:
        """Mark the customer main menu as the current navigation location."""
        await self.preference_service.set_preference(
            user_id,
            PreferenceKey.LAST_MENU,
            CustomerMenuItem.MAIN.value,
        )
        return CustomerMenuItem.MAIN

    async def open_destination(
        self,
        user_id: int,
        item: CustomerMenuItem | str,
    ) -> NavigationDestination:
        """Validate *item*, persist it as last_menu, and return metadata."""
        try:
            menu_item = (
                item if isinstance(item, CustomerMenuItem) else CustomerMenuItem(item)
            )
        except ValueError as exc:
            raise ValueError(f"Unknown customer menu item: {item!r}") from exc

        if menu_item == CustomerMenuItem.MAIN:
            raise ValueError("MAIN is not a content destination")

        destination = _DESTINATIONS[menu_item]
        await self.preference_service.set_preference(
            user_id,
            PreferenceKey.LAST_MENU,
            menu_item.value,
        )
        return destination

    async def get_last_menu(self, user_id: int) -> CustomerMenuItem:
        """Return the last known menu, falling back safely to MAIN."""
        raw = await self.preference_service.get_preference(
            user_id,
            PreferenceKey.LAST_MENU,
        )
        if not raw:
            return CustomerMenuItem.MAIN
        try:
            return CustomerMenuItem(raw)
        except ValueError:
            return CustomerMenuItem.MAIN

    @staticmethod
    def destinations() -> tuple[NavigationDestination, ...]:
        """Return all Phase 1.2 customer destinations."""
        return tuple(
            destination
            for destination in _DESTINATIONS.values()
            if destination.item
            in {
                CustomerMenuItem.BUY_VPN,
                CustomerMenuItem.FREE_TRIAL,
                CustomerMenuItem.MY_KEYS,
                CustomerMenuItem.WALLET,
                CustomerMenuItem.PROFILE,
                CustomerMenuItem.SUPPORT,
                CustomerMenuItem.REFER_FRIENDS,
                CustomerMenuItem.MISSIONS,
            }
        )
