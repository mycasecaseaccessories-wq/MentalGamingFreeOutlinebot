"""Customer menu routing and last-menu persistence."""

from __future__ import annotations

from app.models.navigation import CustomerPage
from app.models.user_preference import PreferenceKey
from app.services.base import BaseService


class CustomerNavigationService(BaseService):
    async def open(self, telegram_id: int, page: str | CustomerPage) -> CustomerPage:
        target = CustomerPage(page)
        preference_service = getattr(self, "preference_service", None)
        if preference_service is not None:
            await preference_service.set_preference(
                telegram_id, PreferenceKey.LAST_MENU, target.value
            )
        return target

    async def last_page(self, telegram_id: int) -> CustomerPage:
        preference_service = getattr(self, "preference_service", None)
        if preference_service is None:
            return CustomerPage.HOME
        value = await preference_service.get_preference(telegram_id, PreferenceKey.LAST_MENU)
        try:
            return CustomerPage(value)
        except (TypeError, ValueError):
            return CustomerPage.HOME

    def configure_dependencies(self, *, preference_service) -> None:
        self.preference_service = preference_service