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
from .admin_server import register as register_admin_server
from .admin_outline import register as register_admin_outline
from .admin_maintenance import register as register_admin_maintenance
from .error import register as register_error
from .customer_navigation import register as register_customer_navigation
from .customer_account import register as register_customer_account
from .package_catalog import register as register_package_catalog
from .customer_keys import register as register_customer_keys
from .router import get_menu_type, get_welcome_flow, MenuType

__all__ = [
    "register_start",
    "register_admin",
    "register_admin_server",
    "register_admin_outline",
    "register_admin_maintenance",
    "register_error",
    "register_customer_navigation",
    "register_customer_account",
    "register_package_catalog",
    "register_customer_keys",
    "get_menu_type",
    "get_welcome_flow",
    "MenuType",
]
