"""Read-only customer profile service for Phase 1.3."""

from __future__ import annotations

from app.models.customer_account import ProfileSummary
from app.services.base import BaseService
from app.services.preference_service import PreferenceService
from app.services.user_service import UserService


class ProfileService(BaseService):
    def __init__(
        self,
        db=None,
        user_service: UserService | None = None,
        preference_service: PreferenceService | None = None,
    ) -> None:
        super().__init__(db)
        self.user_service = user_service or UserService(db)
        self.preference_service = preference_service or PreferenceService(db)

    async def get_customer_profile(self, telegram_id: int) -> ProfileSummary | None:
        user = await self.user_service.get_profile(telegram_id)
        if user is None:
            return None
        preferences = await self.preference_service.get_all_preferences(telegram_id)
        return ProfileSummary(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            status=user.status.value,
            language=user.language.value,
            created_at=user.created_at,
            last_active=user.last_active,
            preferred_currency=str(getattr(preferences, "preferred_currency", "MMK")),
            notification_enabled=bool(getattr(preferences, "notification_enabled", True)),
            broadcast_enabled=bool(getattr(preferences, "broadcast_enabled", True)),
        )
