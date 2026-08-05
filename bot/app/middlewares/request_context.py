"""
Request Context Middleware.

Stamps every incoming Telegram update with a unique request_id and a
RequestContext before any handler sees it.  The context is accessible
anywhere in the async call chain via:

    from app.observability import request_ctx
    ctx = request_ctx.get()
    logger.info("...", extra={"request_id": ctx.request_id})

What this middleware does
-------------------------
1. Creates a new RequestContext (generates request_id).
2. Activates it in the current async task via ContextVar.
3. Increments the global updates-received counter.
4. Stores the context in context.user_data["request_context"] so handlers
   can access it without importing contextvars.
5. Logs the incoming update type at DEBUG level.

Registration
------------
Add as a TypeHandler at group=-2 (before auth/language/activity at -1):

    from app.middlewares.request_context import request_context_middleware_handler
    application.add_handler(
        TypeHandler(Update, request_context_middleware_handler), group=-2
    )

Phase 0.5: Full implementation.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.observability import new_request_context, metrics, request_ctx

logger = logging.getLogger(__name__)

#: context.user_data key where the RequestContext is stored.
REQUEST_CONTEXT_KEY = "request_context"


async def request_context_middleware_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Middleware: stamp every Telegram update with a unique RequestContext.

    Runs at group=-2, before all other middlewares.
    """
    # 1. Create and activate request context.
    ctx = new_request_context()

    # 2. Store in user_data for handler access (no contextvars needed).
    if context.user_data is not None:
        context.user_data[REQUEST_CONTEXT_KEY] = ctx

    # 3. Track metrics.
    metrics.increment("bot.updates.received")
    update_type = _update_type(update)
    metrics.increment(f"bot.updates.{update_type}")

    # 4. Debug log with request_id.
    logger.debug(
        "[%s] Incoming update — type=%s user_id=%s",
        ctx.request_id,
        update_type,
        update.effective_user.id if update.effective_user else "unknown",
    )


def _update_type(update: Update) -> str:
    """Return a short string describing the update type."""
    if update.message:
        if update.message.text:
            return "message.text"
        return "message.other"
    if update.callback_query:
        return "callback_query"
    if update.inline_query:
        return "inline_query"
    if update.edited_message:
        return "edited_message"
    if update.channel_post:
        return "channel_post"
    return "unknown"


def get_request_context(context: ContextTypes.DEFAULT_TYPE):
    """
    Return the RequestContext stored by the middleware, or None.

    Use this helper in handlers instead of importing contextvars directly.

    Args:
        context: PTB handler context.

    Returns:
        RequestContext or None if middleware was not registered.
    """
    if context.user_data is None:
        return None
    return context.user_data.get(REQUEST_CONTEXT_KEY)
