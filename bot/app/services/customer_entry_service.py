"""Phase 1.1 customer entry orchestration.

This service owns start-flow decisions and contains no Telegram UI code.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.events import EventType, bus
from app.models.customer_entry import EntryDecision, EntryRoute
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.models.user_preference import PreferenceKey
from app.services.base import BaseService
from app.services.preference_service import PreferenceService
from app.services.user_service import UserService
from app.services.admin_authorization_service import AdminAuthorizationService

logger = logging.getLogger(__name__)

_START_PARAM_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class CustomerEntryService(BaseService):
    """Resolve registration, onboarding state, account status and UI route."""

    def __init__(
        self,
        db=None,
        user_service: Optional[UserService] = None,
        preference_service: Optional[PreferenceService] = None,
        authorization_service: Optional[AdminAuthorizationService] = None,
    ) -> None:
        super().__init__(db)
        self.user_service = user_service or UserService(db)
        self.preference_service = preference_service or PreferenceService(db)
        self.authorization_service = authorization_service

    @staticmethod
    def sanitize_start_parameter(raw: str | None) -> str | None:
        """Return a safe Telegram deep-link token or None."""
        if not raw:
            return None
        value = raw.strip()
        return value if _START_PARAM_RE.fullmatch(value) else None

    async def resolve(
        self,
        *,
        user: User,
        is_new_user: bool,
        admin_ids: set[int] | frozenset[int] | list[int] | tuple[int, ...],
        start_parameter: str | None = None,
    ) -> EntryDecision:
        """Return the transport-neutral routing decision for `/start`."""
        safe_param = self.sanitize_start_parameter(start_parameter)

        authorized_admin = False
        if self.authorization_service is not None:
            principal = await self.authorization_service.ensure_bootstrap_admin(
                user.telegram_id, admin_ids
            )
            if principal is None:
                principal = await self.authorization_service.resolve_principal(user.telegram_id)
            authorized_admin = bool(
                principal is not None
                and principal.status == "active"
            )
        else:
            # Compatibility path for pre-Phase-8 isolated callers only. The
            # production registry always supplies authorization_service.
            admin_set = set(admin_ids)
            if user.telegram_id in admin_set and user.role != UserRole.ADMIN:
                updated = await self.user_service.change_role(
                    user.telegram_id, UserRole.ADMIN.value
                )
                if updated is not None:
                    user = updated
                authorized_admin = True
            else:
                authorized_admin = user.role == UserRole.ADMIN

        if user.status in {UserStatus.BANNED, UserStatus.SUSPENDED}:
            key = "auth.banned" if user.status == UserStatus.BANNED else "auth.suspended"
            await bus.emit(
                EventType.USER_STARTED_BOT,
                telegram_id=user.telegram_id,
                role=user.role.value,
                status=user.status.value,
                allowed=False,
            )
            return EntryDecision(
                route=EntryRoute.ACCESS_RESTRICTED,
                telegram_id=user.telegram_id,
                role=user.role,
                status=user.status,
                language=user.language.value,
                is_new_user=is_new_user,
                start_parameter=safe_param,
                restriction_key=key,
            )

        preferences, _ = await self.preference_service.get_or_create(user.telegram_id)
        if not preferences.language_selected:
            return EntryDecision(
                route=EntryRoute.LANGUAGE_SELECTION,
                telegram_id=user.telegram_id,
                role=user.role,
                status=user.status,
                language=preferences.language,
                is_new_user=is_new_user,
                start_parameter=safe_param,
            )

        route = EntryRoute.ADMIN if authorized_admin else self._role_route(
            UserRole.CUSTOMER if user.role == UserRole.ADMIN else user.role
        )
        await bus.emit(
            EventType.USER_STARTED_BOT,
            telegram_id=user.telegram_id,
            role=user.role.value,
            status=user.status.value,
            allowed=True,
            start_parameter=safe_param,
        )
        return EntryDecision(
            route=route,
            telegram_id=user.telegram_id,
            role=user.role,
            status=user.status,
            language=preferences.language,
            is_new_user=is_new_user,
            start_parameter=safe_param,
        )

    async def select_language(self, user: User, language_code: str) -> EntryDecision:
        """Persist explicit language choice and continue routing immediately."""
        if language_code not in {"en", "my"}:
            raise ValueError("Unsupported language")

        await self.preference_service.set_preferences(
            user.telegram_id,
            {
                PreferenceKey.LANGUAGE: language_code,
                PreferenceKey.LANGUAGE_SELECTED: True,
            },
        )
        updated = await self.user_service.change_language(user.telegram_id, language_code)
        if updated is not None:
            user = updated

        await bus.emit(
            EventType.USER_LANGUAGE_CHANGED,
            telegram_id=user.telegram_id,
            language=language_code,
        )
        await bus.emit(
            EventType.USER_STARTED_BOT,
            telegram_id=user.telegram_id,
            role=user.role.value,
            status=user.status.value,
            allowed=True,
        )
        return EntryDecision(
            route=self._role_route(user.role),
            telegram_id=user.telegram_id,
            role=user.role,
            status=user.status,
            language=language_code,
        )

    @staticmethod
    def _role_route(role: UserRole) -> EntryRoute:
        mapping = {
            UserRole.ADMIN: EntryRoute.ADMIN,
            UserRole.CUSTOMER: EntryRoute.CUSTOMER,
            UserRole.RESELLER: EntryRoute.RESELLER,
            UserRole.AFFILIATE: EntryRoute.AFFILIATE,
            UserRole.MODERATOR: EntryRoute.MODERATOR,
            UserRole.VIP: EntryRoute.VIP,
        }
        return mapping.get(role, EntryRoute.CUSTOMER)
