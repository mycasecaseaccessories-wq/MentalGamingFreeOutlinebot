"""
Authentication middleware.

Resolves the platform User record for every incoming update and attaches
it to context.user_data so handlers can access it without hitting the DB
themselves.

Implementation: Phase 0.2 (once UserRepository is wired up).
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Resolve and cache the platform user for the current update.

    After this runs, handlers can access the user via:
        user: User = context.user_data.get("platform_user")

    TODO (Phase 0.2):
        1. Extract telegram_id from update.effective_user.
        2. Call UserService.get_or_create().
        3. Store the result in context.user_data["platform_user"].
        4. Block the update if is_active == False.
    """
    logger.debug("auth_middleware — stub (Phase 0.2)")
