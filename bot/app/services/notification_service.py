"""
NotificationService — multi-channel notification dispatch.

Responsibilities (Phase 1+):
  • Send Telegram messages to individual users.
  • Broadcast announcements to all active users.
  • Send structured admin alerts.
  • Queue and rate-limit outgoing messages to respect Telegram API limits.
"""

from __future__ import annotations

from telegram import Bot

from .base import BaseService


class NotificationService(BaseService):
    """Dispatches notifications via the Telegram Bot API."""

    def __init__(self, bot: Bot, **kwargs) -> None:
        """
        Initialise with a Telegram Bot instance.

        Args:
            bot: Authenticated python-telegram-bot Bot object.
        """
        super().__init__(**kwargs)
        self.bot = bot

    async def send_message(self, telegram_id: int, text: str, **kwargs) -> None:
        """
        Send a plain-text or HTML message to a single user.

        Args:
            telegram_id: Recipient Telegram user ID.
            text:        Message body (HTML tags allowed when parse_mode=HTML).
            **kwargs:    Additional kwargs forwarded to Bot.send_message().
        """
        # TODO (Phase 1): add rate-limiting, retry logic, and i18n
        raise NotImplementedError("NotificationService.send_message — Phase 1")

    async def broadcast(self, text: str, role_filter: str | None = None) -> int:
        """
        Send a message to all (optionally role-filtered) active users.

        Args:
            text:        Broadcast message body.
            role_filter: If provided, only users with this role receive the message.

        Returns:
            Number of successfully delivered messages.
        """
        # TODO (Phase 1): paginate user list, send with delay between batches
        raise NotImplementedError("NotificationService.broadcast — Phase 1")

    async def notify_admins(self, text: str) -> None:
        """Send an alert to all configured admin users."""
        # TODO (Phase 1): iterate settings.admin_ids, call send_message()
        raise NotImplementedError("NotificationService.notify_admins — Phase 1")
