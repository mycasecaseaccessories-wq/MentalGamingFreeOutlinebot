"""
Shared pytest fixtures for the Mental Outline VPN Platform test suite.

Hierarchy:
  conftest.py          ← This file — session/module-level shared fixtures
  unit/conftest.py     ← Pure unit fixtures (no I/O)
  integration/conftest.py  ← DB-backed fixtures
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    """Use the default asyncio event loop policy for all tests."""
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# Shared mock objects
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bot() -> MagicMock:
    """Bare Telegram Bot mock — does not make real API calls."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    bot.id = 123456789
    bot.username = "test_bot"
    return bot


@pytest.fixture
def mock_update() -> MagicMock:
    """Minimal telegram.Update mock suitable for handler tests."""
    update = MagicMock()
    update.update_id = 1
    update.effective_user = MagicMock()
    update.effective_user.id = 999_000_001
    update.effective_user.first_name = "TestUser"
    update.effective_user.username = "testuser"
    update.effective_user.is_bot = False
    update.effective_chat = MagicMock()
    update.effective_chat.id = 999_000_001
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture
def mock_context(mock_bot: MagicMock) -> MagicMock:
    """Minimal telegram.ext.CallbackContext mock."""
    ctx = MagicMock()
    ctx.bot = mock_bot
    ctx.bot_data = {}
    ctx.user_data = {}
    ctx.chat_data = {}
    ctx.args = []
    return ctx
