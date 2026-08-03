"""
Middlewares package.

Middlewares are cross-cutting concerns applied to every (or many) incoming
updates before the handler sees them.

Registration order in main.py (TypeHandler at group=-1):
  1. auth_middleware_handler    — Resolve platform User; block banned accounts.
  2. language_middleware_handler — Attach language-bound Translator to context.
  3. activity_middleware_handler — Stamp last_active timestamp.

The role middleware is used as a building block inside handler decorators
(role_required, admin_required) rather than as a standalone TypeHandler.

Available middleware functions:
    auth_middleware_handler     — Authentication and user registration.
    language_middleware_handler — Language resolution and Translator injection.
    activity_middleware_handler — Last-active timestamp tracking.

Available helpers:
    check_role(update, context, role)  — Verify user has required role.
    check_admin(update, context)       — Verify user is admin.
    get_resolved_user(context)         — Return platform User or None.

Context keys set by middlewares:
    "platform_user"  — app.models.user.User instance.
    "translator"     — locales.translator.Translator instance.
"""

from .auth import auth_middleware_handler, PLATFORM_USER_KEY, TRANSLATOR_KEY
from .language import language_middleware_handler
from .activity import activity_middleware_handler
from .role import check_role, check_admin, get_resolved_user

__all__ = [
    # Middleware handlers (registered as TypeHandler in main.py)
    "auth_middleware_handler",
    "language_middleware_handler",
    "activity_middleware_handler",
    # Role helpers (used by decorators)
    "check_role",
    "check_admin",
    "get_resolved_user",
    # Context keys
    "PLATFORM_USER_KEY",
    "TRANSLATOR_KEY",
]
