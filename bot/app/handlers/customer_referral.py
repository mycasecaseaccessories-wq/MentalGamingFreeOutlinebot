from __future__ import annotations

from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import log_handler
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.referral_service import ReferralService
from locales.translator import t


def _service(context: ContextTypes.DEFAULT_TYPE) -> ReferralService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(ReferralService) if registry else context.bot_data.get("referral_service")


def _user(context: ContextTypes.DEFAULT_TYPE):
    return context.user_data.get(PLATFORM_USER_KEY) if context.user_data is not None else None


def _lang(user) -> str:
    value = getattr(getattr(user, "language", None), "value", getattr(user, "language", "en"))
    return value if value in {"en", "my"} else "en"


def _keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("referral.share_link", language=language), callback_data="ref:share")],
        [InlineKeyboardButton(t("referral.my_referrals", language=language), callback_data="ref:history")],
        [InlineKeyboardButton(t("common.back", language=language), callback_data="nav:home")],
    ])


async def _bot_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    username = getattr(context.bot, "username", None)
    if username:
        return username
    me = await context.bot.get_me()
    return me.username or ""


@log_handler
async def show_referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _user(context)
    service = _service(context)
    message = update.effective_message
    if user is None or service is None or message is None:
        return
    lang = _lang(user)
    username = await _bot_username(context)
    link_result = await service.personal_link(user.id, username)
    stats_result = await service.stats(user.id)
    if link_result.is_failure or stats_result.is_failure:
        await message.reply_text(t("referral.generic_error", language=lang))
        return
    link = link_result.unwrap()
    stats = stats_result.unwrap()
    await message.reply_text(
        t("referral.invite_body", language=lang, token=link["token"], link=link["link"], **stats),
        reply_markup=_keyboard(lang),
    )


@log_handler
async def referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = _user(context)
    service = _service(context)
    if query is None or user is None or service is None:
        return
    await query.answer()
    lang = _lang(user)
    if query.data == "ref:share":
        username = await _bot_username(context)
        link_result = await service.personal_link(user.id, username)
        if link_result.is_failure:
            await query.answer(t("referral.generic_error", language=lang), show_alert=True)
            return
        link = link_result.unwrap()["link"]
        share_url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(t('referral.invite_title', language=lang), safe='')}"
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("referral.share_link", language=lang), url=share_url)],
            [InlineKeyboardButton(t("referral.my_referrals", language=lang), callback_data="ref:history")],
            [InlineKeyboardButton(t("common.back", language=lang), callback_data="nav:home")],
        ]))
        return
    if query.data == "ref:history":
        result = await service.history(user.id)
        if result.is_failure:
            await query.answer(t("referral.generic_error", language=lang), show_alert=True)
            return
        items = result.unwrap()["items"]
        if not items:
            text = t("referral.no_referrals", language=lang)
        else:
            lines = [t("referral.history_title", language=lang), ""]
            for index, item in enumerate(items, 1):
                status_key = {
                    "pending_qualification": "referral.pending",
                    "qualified": "referral.qualified",
                    "rewarded": "referral.rewarded",
                    "invalid": "referral.invalid",
                }.get(item["status"], "referral.pending")
                lines.append(f"{t('referral.friend', language=lang, number=index)} — {t(status_key, language=lang)}")
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("common.back", language=lang), callback_data="ref:menu")]]))
        return
    if query.data == "ref:menu":
        await query.edit_message_text(t("referral.invite_title", language=lang), reply_markup=_keyboard(lang))


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(referral_callback, pattern=r"^ref:(menu|share|history)$"), group=12)
