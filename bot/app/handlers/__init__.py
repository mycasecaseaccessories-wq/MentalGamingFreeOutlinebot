"""
Handlers package.

Each module registers one logical group of Telegram update handlers.

Registration pattern:
    Every module exposes a `register(application)` function that
    adds its handlers to the given `Application` instance.

Current modules:
    start   — /start and /help commands; entry point for new users.
    admin   — Admin-only commands (/admin, /stats, etc.).
    error   — Global error handler registered last on the application.

Adding a new handler group:
    1. Create app/handlers/my_feature.py with a `register(application)` fn.
    2. Import and call it in main.py alongside the other register() calls.
"""

from .start import register as register_start
from .admin import register as register_admin
from .error import register as register_error
from .router import get_menu_type, get_welcome_flow, MenuType

__all__ = [
    "register_start",
    "register_admin",
    "register_error",
    "get_menu_type",
    "get_welcome_flow",
    "MenuType",
]
