"""Phase 6.6 Admin Growth Control Center."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import permission_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.growth_reward_service import GrowthRewardService
from app.services.growth_reconciliation_service import GrowthReconciliationService
from app.services.referral_analytics_service import ReferralAnalyticsService
from app.services.referral_risk_service import ReferralRiskService
from locales.translator import t


def _actor(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = (context.user_data or {}).get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", None) or getattr(user, "language", None)
    return value if value in {"en", "my"} else "en"


def _services(context: ContextTypes.DEFAULT_TYPE):
    registry = context.bot_data.get("registry")
    if registry is None:
        return None, None, None, None
    return (
        registry.get_or_none(GrowthRewardService),
        registry.get_or_none(ReferralAnalyticsService),
        registry.get_or_none(ReferralRiskService),
        registry.get_or_none(GrowthReconciliationService),
    )


def _keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.growth.overview", language=language), callback_data="admin:growth:overview")],
        [InlineKeyboardButton(t("admin.growth.rewards", language=language), callback_data="admin:growth:rewards")],
        [InlineKeyboardButton(t("admin.growth.entitlements", language=language), callback_data="admin:growth:entitlements")],
        [InlineKeyboardButton(t("admin.growth.analytics", language=language), callback_data="admin:growth:analytics")],
        [InlineKeyboardButton(t("admin.growth.risk", language=language), callback_data="admin:growth:risk")],
        [InlineKeyboardButton(t("admin.growth.reconcile", language=language), callback_data="admin:growth:reconcile")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:home")],
    ])


async def _render_menu(message, language: str) -> None:
    await message.reply_text(t("admin.growth.menu", language=language), reply_markup=_keyboard(language))


@permission_required("manage_rewards")
async def admin_growth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.effective_message
    actor_id = _actor(update)
    if query is None or message is None or actor_id is None:
        return
    await query.answer()
    language = _lang(context)
    growth, analytics, risk, reconciliation = _services(context)
    if growth is None:
        await message.reply_text(t("common.error", language=language))
        return
    parts = (query.data or "").split(":")
    if parts == ["admin", "growth", "menu"]:
        await _render_menu(message, language)
        return
    if parts == ["admin", "growth", "overview"]:
        result = await growth.admin_overview(actor_id)
        if not result.is_success:
            await message.reply_text(t("admin.growth.permission_denied", language=language))
            return
        data = result.unwrap()
        await message.reply_text(t(
            "admin.growth.summary", language=language,
            total=data["total_rewards"], granted=data["granted"], pending=data["pending"],
            held=data["held"], failed=data["failed"], entitlements=data["entitlements"],
        ), reply_markup=_keyboard(language))
        return
    if parts == ["admin", "growth", "rewards"]:
        result = await growth.admin_reward_search(actor_id, limit=30)
        if not result.is_success:
            await message.reply_text(t("admin.growth.permission_denied", language=language))
            return
        rows = result.unwrap()
        text = t("admin.growth.rewards", language=language)
        for row in rows[:20]:
            text += f"\n\n{row['public_reward_id']} · {row['source_type']} · {row['reward_label']} · {row['status']}"
        await message.reply_text(text, reply_markup=_keyboard(language))
        return
    if parts == ["admin", "growth", "entitlements"]:
        result = await growth.admin_reward_search(actor_id, limit=1)
        if not result.is_success:
            await message.reply_text(t("admin.growth.permission_denied", language=language))
            return
        overview = (await growth.admin_overview(actor_id)).unwrap()
        await message.reply_text(
            f"{t('admin.growth.entitlements', language=language)}\n\n"
            f"Total: {overview['entitlements']}\nAvailable: {overview['available_entitlements']}",
            reply_markup=_keyboard(language),
        )
        return
    if parts == ["admin", "growth", "analytics"] and analytics is not None:
        result = await analytics.dashboard(actor_user_id=actor_id, period="last_30_days")
        if not result.is_success:
            await message.reply_text(t("admin.growth.permission_denied", language=language))
            return
        data = result.unwrap()
        funnel = data.get("funnel", data)
        await message.reply_text(
            f"{t('admin.growth.analytics', language=language)}\n\n"
            f"Attributed: {funnel.get('attributed', 0)}\n"
            f"Qualified: {funnel.get('qualified', 0)}\n"
            f"Rewarded: {funnel.get('rewarded', 0)}\n"
            f"Paid: {funnel.get('paid', 0)}",
            reply_markup=_keyboard(language),
        )
        return
    if parts == ["admin", "growth", "risk"] and risk is not None:
        result = await risk.get_review_candidates(actor_user_id=actor_id, status="open", limit=30)
        if not result.is_success:
            await message.reply_text(t("admin.growth.permission_denied", language=language))
            return
        rows = result.unwrap()
        text = t("admin.growth.risk", language=language)
        if not rows:
            text += "\n\n" + t("admin.referrals.risk_none", language=language)
        for row in rows[:20]:
            text += f"\n\n{row.get('public_observation_id', '—')} · {row.get('signal_type', '—')} · {row.get('risk_level', '—')}"
        await message.reply_text(text, reply_markup=_keyboard(language))
        return
    if parts == ["admin", "growth", "reconcile"] and reconciliation is not None:
        result = await reconciliation.scan(actor_user_id=actor_id)
        if not result.is_success:
            await message.reply_text(t("admin.growth.permission_denied", language=language))
            return
        data = result.unwrap()
        await message.reply_text(
            f"{t('admin.growth.reconcile', language=language)}\n\n"
            f"Stale rewards: {data['counts']['stale_rewards']}\n"
            f"Expired entitlements: {data['counts']['expired_entitlements']}",
            reply_markup=_keyboard(language),
        )
        return


def register(application: Application) -> None:
    application.add_handler(
        CallbackQueryHandler(
            admin_growth_callback,
            pattern=r"^admin:growth:(?:menu|overview|rewards|entitlements|analytics|risk|reconcile)$",
        ),
        group=7,
    )
