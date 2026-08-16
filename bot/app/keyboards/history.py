"""Inline keyboards for Phase 2.5 customer history pages."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from locales.translator import t


def history_list_keyboard(language: str, *, kind: str, page: int, has_previous: bool, has_next: bool, ids: list[str] | None = None) -> InlineKeyboardMarkup:
    rows = []
    for public_id in ids or []:
        rows.append([InlineKeyboardButton(f"🔍 {public_id}", callback_data=f"history:{kind}:detail:{public_id}")])
    pager = []
    if has_previous:
        pager.append(InlineKeyboardButton(t("nav.previous", language=language), callback_data=f"history:{kind}:page:{page - 1}"))
    if has_next:
        pager.append(InlineKeyboardButton(t("nav.next", language=language), callback_data=f"history:{kind}:page:{page + 1}"))
    if pager:
        rows.append(pager)
    rows.append([InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")])
    return InlineKeyboardMarkup(rows)


def history_detail_keyboard(language: str, *, kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("nav.back", language=language), callback_data=f"history:{kind}:page:1")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])
