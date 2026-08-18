"""
NotificationService — multi-channel notification dispatch.

Responsibilities (Phase 1+):
  • Send Telegram messages to individual users.
  • Broadcast announcements to all active users.
  • Send structured admin alerts.
  • Queue and rate-limit outgoing messages to respect Telegram API limits.
"""

from __future__ import annotations

import asyncio
import logging
from telegram import Bot

logger = logging.getLogger(__name__)

from .base import BaseService


class NotificationService(BaseService):
    """Dispatches notifications via the Telegram Bot API."""

    def __init__(self, bot: Bot, *, settings=None, **kwargs) -> None:
        """
        Initialise with a Telegram Bot instance.

        Args:
            bot: Authenticated python-telegram-bot Bot object.
        """
        super().__init__(**kwargs)
        self.bot = bot
        self.settings = settings
        self.max_retries = 3
        self.last_delivery: dict[str, object] | None = None

    async def send_message(self, telegram_id: int, text: str, **kwargs) -> dict:
        """
        Send a plain-text or HTML message to a single user.

        Args:
            telegram_id: Recipient Telegram user ID.
            text:        Message body (HTML tags allowed when parse_mode=HTML).
            **kwargs:    Additional kwargs forwarded to Bot.send_message().
        """
        safe_text = str(text)[:4096]
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.bot.send_message(chat_id=telegram_id, text=safe_text, **kwargs)
                result = {"delivered": True, "telegram_id": telegram_id, "attempts": attempt}
                self.last_delivery = result
                return result
            except Exception as exc:
                last_error = type(exc).__name__
                if attempt < self.max_retries:
                    await asyncio.sleep(0.05 * attempt)
        result = {"delivered": False, "telegram_id": telegram_id, "attempts": self.max_retries, "error_code": "telegram_delivery_failed"}
        self.last_delivery = result
        logger.warning("Operational notification delivery failed: %s", last_error)
        return result

    async def broadcast(self, text: str, role_filter: str | None = None) -> int:
        """
        Send a message to all (optionally role-filtered) active users.

        Args:
            text:        Broadcast message body.
            role_filter: If provided, only users with this role receive the message.

        Returns:
            Number of successfully delivered messages.
        """
        if self._db is None:
            return 0
        from sqlalchemy import select
        from database.models.user import UserORM
        async with self._db.session() as session:
            query = select(UserORM.telegram_id).where(UserORM.is_active.is_(True))
            if role_filter:
                query = query.where(UserORM.role == role_filter)
            recipients = list((await session.execute(query)).scalars().all())
        delivered = 0
        for telegram_id in recipients:
            result = await self.send_message(telegram_id, text)
            delivered += int(bool(result.get("delivered")))
        return delivered

    async def notify_admins(self, text: str) -> None:
        """Send an alert to all configured admin users."""
        admin_ids = tuple(getattr(self.settings, "admin_ids", ()) or ())
        results = [await self.send_message(int(admin_id), text) for admin_id in admin_ids]
        return {"attempted": len(results), "delivered": sum(int(bool(item.get("delivered"))) for item in results), "results": results}
