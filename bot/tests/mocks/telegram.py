"""Mock Telegram API objects — no real network calls."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock


class MockBot:
    """Lightweight mock of telegram.Bot."""

    def __init__(self, bot_id: int = 123_456_789, username: str = "test_bot") -> None:
        self.id = bot_id
        self.username = username
        self.send_message = AsyncMock(return_value=MagicMock(message_id=1))
        self.edit_message_text = AsyncMock(return_value=MagicMock(message_id=1))
        self.delete_message = AsyncMock(return_value=True)
        self.answer_callback_query = AsyncMock(return_value=True)
        self.send_photo = AsyncMock(return_value=MagicMock(message_id=2))
        self.get_me = AsyncMock(return_value=MagicMock(id=bot_id, username=username))

    def __repr__(self) -> str:
        return f"MockBot(id={self.id}, username={self.username!r})"


def make_mock_user(
    user_id: int = 999_000_001,
    first_name: str = "TestUser",
    username: str = "testuser",
    is_bot: bool = False,
) -> MagicMock:
    """Create a mock telegram.User."""
    user = MagicMock()
    user.id = user_id
    user.first_name = first_name
    user.last_name = None
    user.username = username
    user.is_bot = is_bot
    user.language_code = "en"
    return user


def make_mock_message(
    message_id: int = 1,
    text: str = "/start",
    user_id: int = 999_000_001,
) -> MagicMock:
    """Create a mock telegram.Message."""
    msg = MagicMock()
    msg.message_id = message_id
    msg.text = text
    msg.reply_text = AsyncMock(return_value=MagicMock(message_id=message_id + 1))
    msg.edit_text = AsyncMock()
    msg.delete = AsyncMock()
    msg.from_user = make_mock_user(user_id=user_id)
    return msg


def make_mock_update(
    update_id: int = 1,
    user_id: int = 999_000_001,
    text: str = "/start",
) -> MagicMock:
    """Create a mock telegram.Update."""
    update = MagicMock()
    update.update_id = update_id
    update.effective_user = make_mock_user(user_id=user_id)
    update.effective_chat = MagicMock(id=user_id, type="private")
    update.message = make_mock_message(text=text, user_id=user_id)
    update.callback_query = None
    return update


def make_mock_callback_query(
    data: str = "action:value",
    user_id: int = 999_000_001,
) -> MagicMock:
    """Create a mock telegram.CallbackQuery."""
    query = MagicMock()
    query.data = data
    query.from_user = make_mock_user(user_id=user_id)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = make_mock_message(user_id=user_id)
    return query


def make_mock_context(bot: MockBot | None = None, **bot_data: Any) -> MagicMock:
    """Create a mock telegram.ext.CallbackContext."""
    ctx = MagicMock()
    ctx.bot = bot or MockBot()
    ctx.bot_data = dict(bot_data)
    ctx.user_data = {}
    ctx.chat_data = {}
    ctx.args = []
    return ctx
