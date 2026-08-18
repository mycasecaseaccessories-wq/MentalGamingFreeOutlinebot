from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import permission_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.events import EventType, bus
from app.services.referral_service import ReferralService
from app.services.referral_reward_service import ReferralRewardService
from app.services.referral_analytics_service import ReferralAnalyticsService
from app.services.referral_risk_service import ReferralRiskService
from app.services.settings_service import SettingsService
from locales.translator import t


def _service(context: ContextTypes.DEFAULT_TYPE) -> ReferralService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(ReferralService) if registry else None


def _analytics(context: ContextTypes.DEFAULT_TYPE) -> ReferralAnalyticsService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(ReferralAnalyticsService) if registry else None


def _risk(context: ContextTypes.DEFAULT_TYPE) -> ReferralRiskService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(ReferralRiskService) if registry else None


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = context.user_data.get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", getattr(user, "language", "en"))
    return value if value in {"en", "my"} else "en"


def _menu(language: str, enabled: bool = True) -> InlineKeyboardMarkup:
    toggle = "off" if enabled else "on"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.referrals.stats", language=language), callback_data="admin:ref:stats"), InlineKeyboardButton(t("admin.referrals.analytics", language=language), callback_data="admin:ref:analytics")],
        [InlineKeyboardButton(t("admin.referrals.enabled" if not enabled else "admin.referrals.disabled", language=language), callback_data=f"admin:ref:toggle:{toggle}")],
        [InlineKeyboardButton(t("admin.referrals.recent", language=language), callback_data="admin:ref:recent")],
        [InlineKeyboardButton(t("admin.referrals.suspicious", language=language), callback_data="admin:ref:review"), InlineKeyboardButton(t("admin.referrals.risk_queue", language=language), callback_data="admin:ref:risk_queue")],
        [InlineKeyboardButton(t("admin.referrals.reward_history", language=language), callback_data="admin:ref:rewards")],
        [InlineKeyboardButton(t("admin.missions.menu", language=language), callback_data="admin:missions:menu")],
        [InlineKeyboardButton(t("common.back", language=language), callback_data="admin:home")],
    ])


@permission_required("manage_referrals")
async def admin_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    service = _service(context)
    analytics = _analytics(context)
    risk = _risk(context)
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
    if parts == ["admin", "ref", "analytics"]:
        if analytics is None:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        actor = context.user_data.get(PLATFORM_USER_KEY)
        result = await analytics.dashboard(actor_user_id=actor.id, period="last_30_days") if actor else None
        if result is None or result.is_failure:
            await query.answer(t("admin.referrals.review_permission_denied", language=language), show_alert=True)
            return
        data = result.unwrap()
        overview = data["overview"]
        funnel = data["funnel"]
        stages = {item["name"]: item["count"] for item in funnel["stages"]}
        text = (f"{t('admin.referrals.analytics', language=language)}\n\n"
                f"{t('admin.referrals.analytics_overview', language=language, attributed=overview['attributed'], qualified=overview['qualified'], rewarded=overview['rewards_granted'], paid=overview['paid_conversions'])}\n\n"
                f"{t('admin.referrals.analytics_rates', language=language, qualification_rate=funnel['rates']['attribution_to_qualification_percent'], reward_rate=funnel['rates']['qualification_to_reward_percent'])}\n\n"
                f"{t('admin.referrals.funnel', language=language)}: " + " → ".join(f"{key}={value}" for key, value in stages.items()))
        await query.edit_message_text(text, reply_markup=_menu(language, bool(await settings.get("referral_enabled", True))))
        return
    if parts == ["admin", "ref", "risk_queue"]:
        if risk is None:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        actor = context.user_data.get(PLATFORM_USER_KEY)
        result = await risk.get_review_candidates(actor_user_id=actor.id, status="open") if actor else None
        if result is None or result.is_failure:
            await query.answer(t("admin.referrals.review_permission_denied", language=language), show_alert=True)
            return
        items = result.unwrap()
        if not items:
            await query.edit_message_text(t("admin.referrals.risk_none", language=language), reply_markup=_menu(language, bool(await settings.get("referral_enabled", True))))
            return
        lines = []
        buttons = []
        for item in items[:10]:
            lines.append(t("admin.referrals.risk_open_item", language=language, observation=item["observation_id"], user=item["user_id"], signal=item["signal_type"], risk=item["risk_level"], action=item["action"]))
            buttons.append([InlineKeyboardButton(t("admin.referrals.review_approve", language=language), callback_data=f"admin:ref:risk:{item['observation_id']}:approve"), InlineKeyboardButton(t("admin.referrals.review_reject", language=language), callback_data=f"admin:ref:risk:{item['observation_id']}:reject")])
            buttons.append([InlineKeyboardButton(t("admin.referrals.review_pending", language=language), callback_data=f"admin:ref:risk:{item['observation_id']}:pending"), InlineKeyboardButton(t("admin.referrals.block_rewards", language=language), callback_data=f"admin:ref:risk:{item['observation_id']}:block")])
            if item.get("reward_id"):
                buttons.append([InlineKeyboardButton(t("admin.referrals.release_reward", language=language), callback_data=f"admin:ref:risk:{item['observation_id']}:release_reward")])
        buttons.append([InlineKeyboardButton(t("common.back", language=language), callback_data="admin:ref:menu")])
        await query.edit_message_text("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))
        return
    if len(parts) == 5 and parts[:3] == ["admin", "ref", "risk"] and parts[4] in {"approve", "reject", "pending", "release_reward", "block", "unblock"}:
        if risk is None:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        actor = context.user_data.get(PLATFORM_USER_KEY)
        result = await risk.resolve_review(actor_user_id=actor.id, public_observation_id=parts[3], decision=parts[4]) if actor else None
        if result is None or result.is_failure:
            await query.answer(t("admin.referrals.review_not_found", language=language), show_alert=True)
            return
        await query.edit_message_text(t("admin.referrals.review_resolved", language=language, decision=parts[4]), reply_markup=_menu(language, bool(await settings.get("referral_enabled", True))))
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
    if parts == ["admin", "ref", "review"]:
        result = await service.admin_review_queue()
        if result.is_failure:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        items = result.unwrap()
        if not items:
            text = t("admin.referrals.suspicious", language=language) + "\n\n" + t("referral.no_referrals", language=language)
            markup = _menu(language, bool(await settings.get("referral_enabled", True)))
        else:
            text = t("admin.referrals.suspicious", language=language) + "\n\n" + "\n".join(f"{i['public_referral_id']} — {t('admin.referrals.review_required', language=language)}" for i in items)
            buttons = [[InlineKeyboardButton("✅", callback_data=f"admin:ref:review_action:{i['public_referral_id']}:approve"), InlineKeyboardButton("❌", callback_data=f"admin:ref:review_action:{i['public_referral_id']}:reject")] for i in items]
            buttons.append([InlineKeyboardButton(t("common.back", language=language), callback_data="admin:ref:menu")])
            markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, reply_markup=markup)
        return
    if len(parts) == 5 and parts[:3] == ["admin", "ref", "review_action"] and parts[4] in {"approve", "reject", "pending"}:
        actor = context.user_data.get(PLATFORM_USER_KEY)
        public_id, decision = parts[3], parts[4]
        result = await service.review(actor_user_id=actor.id, public_referral_id=public_id, decision=decision)
        if result.is_failure:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        await query.edit_message_text(t("admin.referrals.reward_granted" if decision == "approve" else "admin.referrals.invalid", language=language), reply_markup=_menu(language, bool(await settings.get("referral_enabled", True))))
        return
    if parts == ["admin", "ref", "rewards"]:
        registry = context.bot_data.get("registry")
        rewards = registry.get_or_none(ReferralRewardService) if registry else None
        actor = context.user_data.get(PLATFORM_USER_KEY)
        if rewards is None or actor is None:
            await query.answer(t("referral.generic_error", language=language), show_alert=True)
            return
        result = await rewards.get_reward_history(actor.id)
        rows = result.unwrap() if result.is_success else []
        text = t("admin.referrals.reward_history", language=language) + "\n\n" + ("\n".join(f"{r['public_reward_id']} — {r['status']}" for r in rows) or t("referral.no_referrals", language=language))
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
    application.add_handler(CallbackQueryHandler(admin_referral_callback, pattern=r"^admin:ref:(?:menu|stats|analytics|recent|review|risk_queue|rewards|toggle:(?:on|off)|review_action:[A-Za-z0-9-]+:(?:approve|reject|pending)|risk:OBS-[A-Z0-9-]+:(?:approve|reject|pending|release_reward|block|unblock)|invalidate:[A-Za-z0-9-]+:[A-Za-z0-9_]+)$"), group=7)
