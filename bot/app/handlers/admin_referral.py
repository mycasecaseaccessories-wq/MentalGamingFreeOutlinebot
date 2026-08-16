from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import admin_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.events import EventType, bus
from app.services.referral_service import ReferralService
from app.services.settings_service import SettingsService
from locales.translator import t


def _service(context: ContextTypes.DEFAULT_TYPE) -> ReferralService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(ReferralService) if registry else None


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = context.user_data.get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", getattr(user, "language", "en"))
    return value if value in {"en", "my"} else "en"


def _menu(language: str, enabled: bool = True) -> InlineKeyboardMarkup:
    toggle = "off" if enabled else "on"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.referrals.stats", language=language), callback_data="admin:ref:stats")],
        [InlineKeyboardButton(t("admin.referrals.enabled" if not enabled else "admin.referrals.disabled", language=language), callback_data=f"admin:ref:toggle:{toggle}")],
        [InlineKeyboardButton(t("admin.referrals.recent", language=language), callback_data="admin:ref:recent")],
        [InlineKeyboardButton(t("common.back", language=language), callback_data="admin:home")],
    ])


@admin_required
async def admin_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    service = _service(context)
    registry = context.bot_data.get("registry")
    settings = registry.get_or_none(SettingsService) if registry else None
    if query is None or service is None or settings is None or update.effective_message is None:
        return
    await query.answer()
    language = _lang(context)
    parts = (query.data or "").split(":")
    if parts == ["admin", "ref", "menu"]:
        enabled = bool(await settings.get("referral_enabled", True))
        await query.edit_message_text(t("admin.referrals.menu", language=language), reply_markup=_menu(language, enabled))
        return
    if len(parts) == 4 and parts[:3] == ["admin", "ref", "toggle"] and parts[3] in {"on", "off"}:
        enabled = parts[3] == "on"
        await settings.set("referral_enabled", enabled, type_="bool", category="growth", description="Enable new referral attribution.", is_public=False)
        await bus.emit(EventType.REFERRAL_SYSTEM_ENABLED if enabled else EventType.REFERRAL_SYSTEM_DISABLED, actor_user_id=update.effective_user.id)
        await query.edit_message_text(t("admin.referrals.enabled" if enabled else "admin.referrals.disabled", language=language), reply_markup=_menu(language, enabled))
        return
    if parts == ["admin", "ref", "stats"]:
        result = await service.admin_stats()
        if result.is_failure:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        stats = result.unwrap()
        enabled_label = t("admin.referrals.enabled" if bool(await settings.get("referral_enabled", True)) else "admin.referrals.disabled", language=language)
        text = (f"{t('admin.referrals.menu', language=language)}\n\n"
                f"{enabled_label}\n"
                f"{t('admin.referrals.total', language=language)}: {stats['total']}\n"
                f"{t('admin.referrals.pending', language=language)}: {stats['pending']}\n"
                f"{t('admin.referrals.qualified', language=language)}: {stats['qualified']}\n"
                f"{t('admin.referrals.rewarded', language=language)}: {stats['rewarded']}\n"
                f"{t('admin.referrals.invalid', language=language)}: {stats['invalid']}")
        await query.edit_message_text(text, reply_markup=_menu(language, bool(await settings.get("referral_enabled", True))))
        return
    if parts == ["admin", "ref", "recent"]:
        result = await service.admin_recent()
        if result.is_failure:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        items = result.unwrap()
        text = t("admin.referrals.recent", language=language) + "\n\n"
        status_keys = {
            "pending_qualification": "referral.pending",
            "qualified": "referral.qualified",
            "rewarded": "referral.rewarded",
            "invalid": "referral.invalid",
        }
        source_keys = {
            "personal_link": "admin.referrals.source_personal_link",
            "start_payload": "admin.referrals.source_start_payload",
        }
        text += "\n".join(
            f"{item['public_referral_id']} — {t(status_keys.get(item['status'], 'referral.pending'), language=language)} — "
            f"{t(source_keys.get(item['source'], 'admin.referrals.source'), language=language)}"
            for item in items
        ) or t("referral.no_referrals", language=language)
        await query.edit_message_text(text, reply_markup=_menu(language, bool(await settings.get("referral_enabled", True))))
        return
    if len(parts) == 5 and parts[:3] == ["admin", "ref", "invalidate"]:
        actor = context.user_data.get(PLATFORM_USER_KEY)
        result = await service.invalidate(actor_user_id=actor.id, public_referral_id=parts[3], reason=parts[4])
        if result.is_failure:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        await query.edit_message_text(t("admin.referrals.invalidated", language=language, referral=parts[3]), reply_markup=_menu(language, bool(await settings.get("referral_enabled", True))))


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(admin_referral_callback, pattern=r"^admin:ref:(?:menu|stats|recent|toggle:(?:on|off)|invalidate:[A-Za-z0-9-]+:[A-Za-z0-9_]+)$"), group=7)
