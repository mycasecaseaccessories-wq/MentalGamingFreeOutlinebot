"""Admin server management keyboards for Phase 3.1."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from locales.translator import t


def server_menu_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.servers.add", language=language), callback_data="admin:servers:add")],
        [InlineKeyboardButton(t("admin.servers.list", language=language), callback_data="admin:servers:list:1")],
        [InlineKeyboardButton(t("admin.servers.status", language=language), callback_data="admin:servers:status")],
        [InlineKeyboardButton(t("admin.servers.capacity", language=language), callback_data="admin:servers:capacity")],
        [InlineKeyboardButton(t("admin.servers.maintenance", language=language), callback_data="admin:servers:maintenance")],
        [InlineKeyboardButton(t("admin.servers.selection_preview", language=language), callback_data="admin:servers:select:paid:SG")],
        [InlineKeyboardButton(t("admin.servers.sync", language=language), callback_data="admin:servers:sync")],
        [InlineKeyboardButton(t("admin.home", language=language), callback_data="admin:home")],
    ])


def server_add_methods_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.servers.method_outline", language=language), callback_data="admin:servers:future:outline")],
        [InlineKeyboardButton(t("admin.servers.method_ssh", language=language), callback_data="admin:servers:future:ssh")],
        [InlineKeyboardButton(t("admin.servers.method_auto", language=language), callback_data="admin:servers:future:auto")],
        [InlineKeyboardButton(t("admin.servers.method_manual", language=language), callback_data="admin:servers:add:manual")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:servers:menu")],
    ])


def server_list_keyboard(language: str, *, page: int, has_previous: bool, has_next: bool, ids: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"🔍 {public_id}", callback_data=f"admin:servers:view:{public_id}")] for public_id in ids]
    pager = []
    if has_previous: pager.append(InlineKeyboardButton(t("nav.previous", language=language), callback_data=f"admin:servers:list:{page - 1}"))
    if has_next: pager.append(InlineKeyboardButton(t("nav.next", language=language), callback_data=f"admin:servers:list:{page + 1}"))
    if pager: rows.append(pager)
    rows.append([InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:servers:menu")])
    return InlineKeyboardMarkup(rows)


def server_detail_keyboard(language: str, *, public_id: str, enabled: bool, maintenance: bool, archived: bool, action_callbacks: dict[str, str] | None = None) -> InlineKeyboardMarkup:
    callbacks = action_callbacks or {}
    rows = []
    if not archived:
        rows.append([InlineKeyboardButton(t("admin.servers.edit", language=language), callback_data=callbacks.get("edit", f"admin:servers:edit:{public_id}"))])
        rows.append([InlineKeyboardButton(t("admin.servers.sync_now", language=language), callback_data=callbacks.get("sync", f"admin:servers:sync:{public_id}"))])
        rows.append([InlineKeyboardButton(t("admin.servers.health_check", language=language), callback_data=callbacks.get("health", f"admin:servers:health:{public_id}"))])
        rows.append([InlineKeyboardButton(t("admin.servers.usage", language=language), callback_data=callbacks.get("usage", f"admin:servers:usage:{public_id}"))])
        action = "disable" if enabled else "enable"
        rows.append([InlineKeyboardButton(t(f"admin.servers.{action}", language=language), callback_data=callbacks.get(action, f"admin:servers:{action}:{public_id}"))])
        maintenance_action = "maintenance_off" if maintenance else "maintenance_on"
        rows.append([InlineKeyboardButton(t(f"admin.servers.{maintenance_action}", language=language), callback_data=callbacks.get(maintenance_action, f"admin:servers:{maintenance_action}:{public_id}"))])
        rows.append([InlineKeyboardButton(t("admin.servers.archive", language=language), callback_data=callbacks.get("archive", f"admin:servers:archive:{public_id}"))])
    rows.append([InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:servers:list:1")])
    return InlineKeyboardMarkup(rows)
