"""
Base handler utilities.

Provides shared decorators and helper functions used across all handler modules.

Phase 0.4:
  • Implemented admin_required, customer_required, role_required, language_required.
  • Kept log_handler and legacy admin_only (backward-compatible stub).

Decorator usage:
    @admin_required
    async def my_admin_handler(update, context):
        ...

    @role_required(UserRole.RESELLER)
    async def reseller_dashboard(update, context):
        ...

    @language_required
    async def lang_sensitive_handler(update, context):
        ...
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from app.models.enums import UserRole

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging decorator
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Role-based access decorators
# ---------------------------------------------------------------------------

def permission_required(permission: str, *, critical: bool = False) -> Callable:
    """Authorize the Telegram sender for one centralized permission key."""
    def decorator(handler: Callable) -> Callable:
        @functools.wraps(handler)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            from app.middlewares.role import check_admin
            if not await check_admin(update, context, permission, critical=critical):
                return
            await handler(update, context)
        return wrapper
    return decorator


def admin_required(handler: Callable) -> Callable:
    """
    Decorator that restricts a handler to Admin users only.

    Sends an error message and returns early when the user is not an admin.

    Usage:
        @admin_required
        async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        from app.middlewares.role import check_admin
        if not await check_admin(update, context):
            return
        await handler(update, context)
    return wrapper


def customer_required(handler: Callable) -> Callable:
    """
    Decorator that restricts a handler to Customer (or higher) users.

    Admins bypass this check and always pass.

    Usage:
        @customer_required
        async def buy_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        from app.middlewares.role import check_role
        if not await check_role(update, context, UserRole.CUSTOMER):
            return
        await handler(update, context)
    return wrapper


def role_required(required_role: UserRole) -> Callable:
    """
    Parameterised decorator that gates a handler behind a specific role.

    Admins always pass, regardless of the required role.

    Args:
        required_role: The minimum UserRole the caller must hold.

    Usage:
        @role_required(UserRole.RESELLER)
        async def reseller_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    def decorator(handler: Callable) -> Callable:
        @functools.wraps(handler)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            from app.middlewares.role import check_role
            if not await check_role(update, context, required_role):
                return
            await handler(update, context)
        return wrapper
    return decorator


def language_required(handler: Callable) -> Callable:
    """
    Decorator that ensures the user has selected a language.

    When no language is detected in context, sends a prompt and returns early.
    Relies on the language middleware having run first.

    Usage:
        @language_required
        async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        from app.middlewares.auth import PLATFORM_USER_KEY
        user = context.user_data.get(PLATFORM_USER_KEY)

        if user is None or user.language is None:
            if update.effective_message:
                from locales.translator import t
                await update.effective_message.reply_text(
                    t("error.language_required", language="en")
                )
            return

        await handler(update, context)
    return wrapper


# ---------------------------------------------------------------------------
# Legacy backward-compatible stub
# ---------------------------------------------------------------------------

def admin_only(handler: Callable) -> Callable:
    """
    Legacy alias for admin_required().

    Kept for backward compatibility with Phase 0.1 code.
    New code should use @admin_required instead.
    """
    return admin_required(handler)
