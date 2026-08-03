"""
Role-based UI router.

Determines which menu type and flow to show based on the user's role.
This is the single place that maps roles to UI surfaces — future roles
only require a new entry here and a new menu builder.

Phase 0.4: Routing architecture prepared; menus implemented in Phase 1.

Usage:
    from app.handlers.router import get_menu_type, MenuType

    menu_type = get_menu_type(user.role)
    if menu_type == MenuType.ADMIN:
        await show_admin_menu(update, context)
    else:
        await show_customer_menu(update, context)
"""

from __future__ import annotations

from enum import Enum, unique

from app.models.enums import UserRole


@unique
class MenuType(str, Enum):
    """
    Identifies which main-menu surface to show the user.

    Phase 1+: Each MenuType maps to a builder function in app/keyboards/.
    """

    ADMIN = "admin"
    CUSTOMER = "customer"
    RESELLER = "reseller"       # Phase 2
    AFFILIATE = "affiliate"     # Phase 2
    MODERATOR = "moderator"     # Phase 2
    VIP = "vip"                 # Phase 2


# ---------------------------------------------------------------------------
# Role → menu mapping
# ---------------------------------------------------------------------------

_ROLE_TO_MENU: dict[str, MenuType] = {
    UserRole.ADMIN:     MenuType.ADMIN,
    UserRole.CUSTOMER:  MenuType.CUSTOMER,
    UserRole.RESELLER:  MenuType.RESELLER,
    UserRole.AFFILIATE: MenuType.AFFILIATE,
    UserRole.MODERATOR: MenuType.MODERATOR,
    UserRole.VIP:       MenuType.VIP,
}


def get_menu_type(role: UserRole) -> MenuType:
    """
    Return the MenuType for *role*.

    Falls back to CUSTOMER for any unknown or future role so the bot
    degrades gracefully without crashing.

    Args:
        role: The user's current UserRole.

    Returns:
        MenuType identifying the UI surface for this role.
    """
    return _ROLE_TO_MENU.get(role, MenuType.CUSTOMER)


def should_show_admin_entry(role: UserRole) -> bool:
    """
    Return True when the user's menu should include an admin-panel button.

    Args:
        role: The user's current UserRole.
    """
    return role == UserRole.ADMIN


def get_welcome_flow(role: UserRole, is_new_user: bool) -> str:
    """
    Return a flow identifier for the /start entry point.

    Values:
        "language_select"  — Brand-new user who has not selected a language.
        "admin_welcome"    — Returning admin user.
        "customer_welcome" — Returning customer.
        "reseller_welcome" — Returning reseller (Phase 2).

    Args:
        role:         The user's role.
        is_new_user:  True when the user was created during this /start call.

    Returns:
        A string flow identifier consumed by the start handler.
    """
    if is_new_user:
        return "language_select"
    if role == UserRole.ADMIN:
        return "admin_welcome"
    return f"{get_menu_type(role).value}_welcome"
