"""Package catalogue inline keyboards."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.package_catalog import PackagePage
from locales.translator import t


def build_package_list_keyboard(page: PackagePage, language: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            f"📦 {item.name}",
            callback_data=f"pkg:view:{item.package_id}",
        )]
        for item in page.items
    ]
    nav = []
    if page.has_previous:
        nav.append(InlineKeyboardButton(t("package.previous", language=language), callback_data=f"pkg:list:{page.page-1}"))
    if page.has_next:
        nav.append(InlineKeyboardButton(t("package.next", language=language), callback_data=f"pkg:list:{page.page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t("package.refresh", language=language), callback_data=f"pkg:list:{page.page}")])
    rows.append([InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")])
    return InlineKeyboardMarkup(rows)


def build_package_details_keyboard(package_id: int, language: str, page: int = 1) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("package.select", language=language), callback_data=f"pkg:select:{package_id}")],
        [InlineKeyboardButton(t("common.back", language=language), callback_data=f"pkg:list:{page}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_package_selected_keyboard(package_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("package.continue_payment", language=language), callback_data="pkg:checkout")],
        [InlineKeyboardButton(t("common.cancel", language=language), callback_data=f"pkg:view:{package_id}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_empty_catalog_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("package.refresh", language=language), callback_data="pkg:list:1")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])
