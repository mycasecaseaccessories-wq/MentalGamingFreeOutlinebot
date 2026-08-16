"""
Middlewares package.

Middlewares are cross-cutting concerns applied to every (or many) incoming
updates before the handler sees them.

Registration order in main.py (TypeHandler, group in parentheses):
  group=-2  request_context_middleware_handler — Stamp update with request_id.
  group=-1  auth_middleware_handler            — Resolve platform User; block banned.
  group=-1  language_middleware_handler        — Attach Translator to context.
  group=-1  activity_middleware_handler        — Stamp last_active timestamp.

The role middleware is used as a building block inside handler decorators
(role_required, admin_required) rather than as a standalone TypeHandler.

Available middleware handlers (registered as TypeHandler):
    request_context_middleware_handler — Per-request ID and context injection.
    auth_middleware_handler            — Authentication and user registration.
    language_middleware_handler        — Language resolution and Translator injection.
    activity_middleware_handler        — Last-active timestamp tracking.

Available helpers:
    check_role(update, context, role)  — Verify user has required role.
    check_admin(update, context)       — Verify user is admin.
    get_resolved_user(context)         — Return platform User or None.
    get_request_context(context)       — Return RequestContext or None.

Context keys set by middlewares:
    "request_context" — app.observability.RequestContext instance.
    "platform_user"   — app.models.user.User instance.
    "translator"      — locales.translator.Translator instance.
"""

from .auth import auth_middleware_handler, PLATFORM_USER_KEY, TRANSLATOR_KEY
from .language import language_middleware_handler
from .activity import activity_middleware_handler
from .role import check_role, check_admin, get_resolved_user
from .request_context import (
    request_context_middleware_handler,
    get_request_context,
    REQUEST_CONTEXT_KEY,
)

__all__ = [
    # Middleware handlers (registered as TypeHandler in main.py)
    "request_context_middleware_handler",
    "auth_middleware_handler",
    "language_middleware_handler",
    "activity_middleware_handler",
    # Role helpers (used by decorators)
    "check_role",
    "check_admin",
    "get_resolved_user",
    # Request context helper
    "get_request_context",
    # Context keys
    "REQUEST_CONTEXT_KEY",
    "PLATFORM_USER_KEY",
    "TRANSLATOR_KEY",
]
