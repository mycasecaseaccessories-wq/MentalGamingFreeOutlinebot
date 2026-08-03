"""
Base handler utilities.

Provides shared decorators and helper functions used across all handler modules.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def admin_only(handler: Callable) -> Callable:
    """
    Decorator that restricts a handler to users with the ADMIN role.

    Usage:
        @admin_only
        async def my_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...

    Note: Full permission enforcement will be implemented in Phase 0.2.
          For now this is a structural placeholder.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # TODO (Phase 0.2): Query UserService to verify role before proceeding.
        logger.debug(
            "admin_only check — user_id=%s handler=%s",
            update.effective_user.id if update.effective_user else "unknown",
            handler.__name__,
        )
        await handler(update, context)

    return wrapper


def log_handler(handler: Callable) -> Callable:
    """
    Decorator that logs handler entry and exit at DEBUG level.

    Useful for tracing user interactions during development.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.debug(
            "→ %s called by user_id=%s username=%s",
            handler.__name__,
            user.id if user else "unknown",
            user.username if user else "unknown",
        )
        await handler(update, context)
        logger.debug("← %s finished", handler.__name__)

    return wrapper
