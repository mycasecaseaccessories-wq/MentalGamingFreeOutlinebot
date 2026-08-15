"""Phase 1.1 customer/admin entry orchestration."""

from __future__ import annotations

import re

from app.models.customer_entry import EntryDecision, EntryRoute
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.services.base import BaseService


class CustomerEntryService(BaseService):
    """Resolve a user into the first safe route after /start."""

    async def resolve(
        self,
        *,
        user: User,
        is_new_user: bool,
        admin_ids: list[int] | tuple[int, ...],
        start_parameter: str | None = None,
    ) -> EntryDecision:
        if user.status in {UserStatus.BANNED, UserStatus.SUSPENDED}:
            return EntryDecision(
                route=EntryRoute.ACCESS_RESTRICTED,
                telegram_id=user.telegram_id,
                role=user.role,
                status=user.status,
                language=user.language.value,
                restriction_key=(
                    "auth.banned" if user.status == UserStatus.BANNED else "auth.suspended"
                ),
            )

        if user.telegram_id in admin_ids:
            if user.role != UserRole.ADMIN and hasattr(self.user_service, "change_role"):
                await self.user_service.change_role(user.telegram_id, UserRole.ADMIN.value)
            role = UserRole.ADMIN
        else:
            role = user.role

        prefs = await self.preference_service.get_or_create(user.telegram_id)
        pref = prefs[0] if isinstance(prefs, tuple) else prefs
        selected = bool(getattr(pref, "language_selected", False))
        if is_new_user or not selected:
            route = EntryRoute.LANGUAGE_SELECTION
        else:
            route = EntryRoute(role.value) if role.value in EntryRoute._value2member_map_ else EntryRoute.CUSTOMER
        return EntryDecision(
            route=route,
            telegram_id=user.telegram_id,
            role=role,
            status=user.status,
            language=getattr(pref, "language", user.language.value),
            is_new_user=is_new_user,
            start_parameter=self.sanitize_start_parameter(start_parameter),
        )

    @staticmethod
    def sanitize_start_parameter(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value)
        return cleaned[:64] or None

    def configure_dependencies(self, *, user_service, preference_service) -> None:
        self.user_service = user_service
        self.preference_service = preference_service