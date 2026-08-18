"""
Role middleware.

Provides a callable that can be composed into the middleware chain to
verify that the current user holds a required role before the update
reaches a handler.

This module does NOT register itself as a TypeHandler; it is used by the
role_required() decorator in app/handlers/base.py.

Phase 0.4: Architecture prepared.  Enforcement active in handler decorators.
"""

from __future__ import annotations

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.middlewares.auth import PLATFORM_USER_KEY
from app.models.enums import UserRole

logger = logging.getLogger(__name__)


async def check_role(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    required_role: UserRole,
) -> bool:
    """
    Return True if the resolved user holds *required_role* (or ADMIN).

    Admins bypass all role checks — they can access any section.
    Sends an error message and returns False when access is denied.

    Args:
        update:        Incoming Telegram update.
        context:       Handler context (must contain platform_user in user_data).
        required_role: Minimum role required to pass the check.

    Returns:
        True when access is granted; False when denied.
    """
    user = context.user_data.get(PLATFORM_USER_KEY)

    if user is None:
        logger.warning("check_role: no platform_user in context — denying access.")
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Authentication required.")
        return False

    # Admins bypass all role restrictions.
    if user.role == UserRole.ADMIN:
        return True

    if user.role != required_role:
        from locales.translator import t
        lang = user.language.value if user.language else "en"
        await update.effective_message.reply_text(t("error.unauthorized", language=lang))
        logger.info(
            "check_role: access denied — user_id=%s role=%s required=%s",
            user.telegram_id, user.role.value, required_role.value,
        )
        return False

    return True


async def check_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    permission: str | None = None,
    *,
    critical: bool = False,
) -> bool:
    """
    Return True if the resolved user is an Admin.

    Convenience wrapper around check_role() for admin-only sections.
    """
    user = context.user_data.get(PLATFORM_USER_KEY)
    if user is None:
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Authentication required.")
        return False

    registry = context.bot_data.get("registry")
    if registry is None:
        logger.warning("check_admin: authorization registry unavailable — denying")
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Action not permitted.")
        return False
    from app.services.admin_authorization_service import AdminAuthorizationService
    service = registry.get_or_none(AdminAuthorizationService)
    if service is None:
        logger.warning("check_admin: authorization service unavailable — denying")
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Action not permitted.")
        return False
    result = await service.authorize(
        user.telegram_id,
        permission,
        chat_type=getattr(getattr(update, "effective_chat", None), "type", None),
        critical=critical,
    )
    if result.is_success:
        context.user_data["admin_principal"] = result.unwrap()
        return True
    if update.effective_message:
        await update.effective_message.reply_text("⛔ Action not permitted.")
    logger.info("check_admin: centralized authorization denied — telegram_id=%s", user.telegram_id)
    return False


def get_resolved_user(context: ContextTypes.DEFAULT_TYPE) -> Optional[object]:
    """
    Return the platform User from context, or None if not resolved yet.

    Safe to call from any handler after the auth middleware has run.
    """
    return context.user_data.get(PLATFORM_USER_KEY)
