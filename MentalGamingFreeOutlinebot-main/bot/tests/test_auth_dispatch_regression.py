"""Regression coverage for dispatcher-level access-control stopping."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ApplicationHandlerStop

# The handlers package imports configuration during collection. These are test-only
# placeholders and are not used for a real Telegram or database connection.
os.environ.setdefault("BOT_TOKEN", "123456:TEST_TOKEN")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

from app.middlewares.auth import PLATFORM_USER_KEY, auth_middleware_handler


@pytest.mark.asyncio
async def test_restricted_non_start_update_stops_before_business_handlers() -> None:
    """A restricted account must stop dispatch after receiving its denial message."""
    platform_user = SimpleNamespace(
        can_use_bot=False,
        language=SimpleNamespace(value="en"),
        is_banned=True,
        status=SimpleNamespace(value="banned"),
        role=SimpleNamespace(value="customer"),
        telegram_id=991,
        username="restricted_user",
        full_name="Restricted User",
    )
    user_service = SimpleNamespace(register_user=AsyncMock(return_value=(platform_user, False)))
    message = SimpleNamespace(text="Open menu", reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=991,
            full_name="Restricted User",
            username="restricted_user",
            first_name="Restricted",
            last_name="User",
        ),
        message=message,
        callback_query=None,
    )
    context = SimpleNamespace(bot_data={"user_service": user_service}, user_data={})

    with pytest.raises(ApplicationHandlerStop):
        await auth_middleware_handler(update, context)

    assert context.user_data[PLATFORM_USER_KEY] is platform_user
    message.reply_text.assert_awaited_once()
