"""Read-only support configuration service for Phase 1.3."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.base import BaseService
from app.services.settings_service import SettingsService


@dataclass(frozen=True, slots=True)
class SupportInfo:
    username: str | None
    channel: str | None
    email: str | None
    hours: str | None
    message: str | None


class SupportService(BaseService):
    def __init__(self, db=None, settings_service: SettingsService | None = None) -> None:
        super().__init__(db)
        self.settings_service = settings_service or SettingsService(db)

    async def get_support_info(self, runtime_settings=None) -> SupportInfo:
        runtime_username = getattr(runtime_settings, "support_username", "") if runtime_settings else ""
        username = await self.settings_service.get("support_username", default=runtime_username)
        channel = await self.settings_service.get("support_channel", default="")
        email = await self.settings_service.get("support_email", default="")
        hours = await self.settings_service.get("support_hours", default="")
        message = await self.settings_service.get("support_message", default="")

        def clean(value):
            text = str(value or "").strip()
            return text or None

        return SupportInfo(
            username=clean(username).lstrip("@") if clean(username) else None,
            channel=clean(channel),
            email=clean(email),
            hours=clean(hours),
            message=clean(message),
        )
