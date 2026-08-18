"""Phase 1.4 customer package catalogue and Buy VPN handlers."""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from telegram import ForceReply, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.handlers.base import log_handler
from app.handlers.customer_navigation import _get_user, _is_customer_surface, _language
from app.middlewares.auth import PLATFORM_USER_KEY
from app.keyboards.package_catalog import (
    build_empty_catalog_keyboard,
    build_package_details_keyboard,
    build_package_list_keyboard,
    build_package_selected_keyboard,
)
from app.keyboards.order import (
    build_cancel_confirmation_keyboard,
    build_cancelled_keyboard,
    build_checkout_keyboard,
    build_order_created_keyboard,
    build_order_details_keyboard,
    build_payment_methods_keyboard,
    build_manual_payment_methods_keyboard,
    build_manual_payment_instruction_keyboard,
    build_manual_payment_waiting_keyboard,
    build_wallet_payment_preview_keyboard,
    build_wallet_payment_result_keyboard,
)
from app.models.order import Order
from app.services.manual_payment_service import ManualPaymentService
from app.services.payment_submission_service import PaymentSubmissionService
from app.models.package_catalog import PackageSelection, PackageSummary
from app.services.callback_security_service import CallbackSecurityService
from app.services.checkout_service import CheckoutService
from app.services.order_service import (
    CheckoutExpiredError,
    CustomerRestrictedError,
    InvalidOrderStateError,
    OrderNotFoundError,
    PackageChangedError,
    OrderService,
)
from app.services.package_catalog_service import PackageCatalogService
from app.services.wallet_payment_service import WalletPaymentService
from locales.translator import t

logger = logging.getLogger(__name__)
_SELECTION_KEY = "phase14_package_selection"
_MANUAL_PAYMENT_KEY = "phase23_manual_payment"


def _service(context: ContextTypes.DEFAULT_TYPE) -> PackageCatalogService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(PackageCatalogService)


def _checkout_service(context: ContextTypes.DEFAULT_TYPE) -> CheckoutService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(CheckoutService)


def _callback_service(context: ContextTypes.DEFAULT_TYPE) -> CallbackSecurityService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(CallbackSecurityService)


def _order_service(context: ContextTypes.DEFAULT_TYPE) -> OrderService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(OrderService)


def _wallet_payment_service(context: ContextTypes.DEFAULT_TYPE) -> WalletPaymentService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(WalletPaymentService)


def _manual_payment_service(context: ContextTypes.DEFAULT_TYPE) -> ManualPaymentService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(ManualPaymentService)


def _payment_submission_service(context: ContextTypes.DEFAULT_TYPE) -> PaymentSubmissionService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(PaymentSubmissionService)


def _manual_method_text(method, order: Order, language: str) -> str:
    public = method.public_fields()
    details = [method.instructions]
    for label, key in (("Account name", "account_name"), ("Account number", "account_number"), ("Phone", "phone_number"), ("Wallet address", "wallet_address"), ("Network", "network")):
        if public.get(key):
            details.append(f"{label}: {public[key]}")
    return t(
        "order.manual_method_instructions",
        language=language,
        method=method.name,
        instructions="\\n".join(details),
        amount=_money(order.total_amount, order.currency),
        order=order.public_order_id,
    )


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return "—"
    normalized = value.normalize()
    return format(normalized, "f").rstrip("0").rstrip(".") if "." in format(normalized, "f") else format(normalized, "f")


def _money(value: Decimal, currency: str) -> str:
    if value == value.to_integral_value():
        return f"{int(value):,} {currency}"
    return f"{value:,.2f} {currency}"


def _summary_line(pkg: PackageSummary, language: str) -> str:
    data = t("package.unlimited", language=language) if pkg.data_limit_gb is None else f"{_format_decimal(pkg.data_limit_gb)} GB"
    devices = t("package.unlimited", language=language) if pkg.device_limit is None else str(pkg.device_limit)
    badge = f" {pkg.badge}" if pkg.badge else ""
    return (
        f"📦 {pkg.name}{badge}\n"
        f"{t('package.data', language=language)}: {data}\n"
        f"{t('package.duration', language=language)}: {pkg.duration_days} {t('package.days', language=language)}\n"
        f"{t('package.devices', language=language)}: {devices}\n"
        f"{t('package.price', language=language)}: {_money(pkg.price, pkg.currency)}"
    )


def _server_label(pkg: PackageSummary, language: str) -> str:
    if pkg.server_policy == "country" and pkg.country:
        return pkg.country
    if pkg.server_policy == "premium":
        return t("package.server_premium", language=language)
    return t("package.server_auto", language=language)


async def _show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> None:
    user = _get_user(context)
    message = update.effective_message
    svc = _service(context)
    if not _is_customer_surface(user) or message is None:
        return
    lang = _language(user)
    if svc is None:
        await message.reply_text(t("common.error", language=lang))
        return
    result = await svc.get_available_packages(page=page)
    if not result.items:
        await message.reply_text(
            t("package.empty", language=lang),
            reply_markup=build_empty_catalog_keyboard(lang),
        )
        return
    text = t("package.catalog_title", language=lang) + "\n\n" + "\n\n".join(
        _summary_line(pkg, lang) for pkg in result.items
    )
    await message.reply_text(text, reply_markup=build_package_list_keyboard(result, lang))


async def _show_details(update: Update, context: ContextTypes.DEFAULT_TYPE, package_id: int) -> None:
    user = _get_user(context); message = update.effective_message; svc = _service(context)
    if not _is_customer_surface(user) or message is None:
        return
    lang = _language(user)
    pkg = None if svc is None else await svc.get_package_details(package_id)
    if pkg is None:
        await message.reply_text(t("package.unavailable", language=lang), reply_markup=build_empty_catalog_keyboard(lang))
        return
    description = pkg.description or t("common.not_set", language=lang)
    data = t("package.unlimited", language=lang) if pkg.data_limit_gb is None else f"{_format_decimal(pkg.data_limit_gb)} GB"
    devices = t("package.unlimited", language=lang) if pkg.device_limit is None else str(pkg.device_limit)
    renewable = t("common.yes" if pkg.renewable else "common.no", language=lang)
    text = "\n".join([
        t("package.details_title", language=lang), "",
        f"{t('package.name', language=lang)}: {pkg.name}",
        f"{t('package.data', language=lang)}: {data}",
        f"{t('package.duration', language=lang)}: {pkg.duration_days} {t('package.days', language=lang)}",
        f"{t('package.devices', language=lang)}: {devices}",
        f"{t('package.price', language=lang)}: {_money(pkg.price, pkg.currency)}",
        f"{t('package.renewable', language=lang)}: {renewable}",
        f"{t('package.server', language=lang)}: {_server_label(pkg, lang)}",
        f"{t('package.description', language=lang)}: {description}",
    ])
    await message.reply_text(text, reply_markup=build_package_details_keyboard(pkg.package_id, lang))


def _checkout_text(selection: PackageSelection, language: str) -> str:
    data = t("package.unlimited", language=language) if selection.data_limit_gb is None else f"{_format_decimal(selection.data_limit_gb)} GB"
    devices = t("package.unlimited", language=language) if selection.device_limit is None else str(selection.device_limit)
    return "\n".join([
        t("order.checkout_title", language=language), "",
        f"{t('package.name', language=language)}: {selection.package_name}",
        f"{t('package.data', language=language)}: {data}",
        f"{t('package.duration', language=language)}: {selection.duration_days} {t('package.days', language=language)}",
        f"{t('package.devices', language=language)}: {devices}",
        f"{t('package.price', language=language)}: {_money(selection.quoted_price, selection.currency)}",
        f"{t('package.server', language=language)}: {_server_label(PackageSummary(selection.package_id, selection.package_name, selection.package_type, selection.quoted_price, selection.currency, selection.data_limit_gb, selection.duration_days, selection.device_limit, 'normal', selection.server_policy, selection.country, True, None, None, 0), language)}",
        "",
        t("order.confirm_prompt", language=language),
    ])


def _order_text(order: Order, language: str, title_key: str = "order.created") -> str:
    snapshot = order.package_snapshot
    data = t("package.unlimited", language=language) if snapshot.data_limit_gb is None else f"{_format_decimal(snapshot.data_limit_gb)} GB"
    devices = t("package.unlimited", language=language) if snapshot.device_limit is None else str(snapshot.device_limit)
    method = order.payment_method.value if order.payment_method else "—"
    status_labels = {
        "waiting_payment": "order.waiting_payment",
        "awaiting_approval": "order.awaiting_approval",
        "paid": "order.paid",
        "completed": "order.completed",
        "cancelled": "order.cancelled",
        "expired": "order.expired",
    }
    payment_labels = {
        "unpaid": "order.payment_unpaid",
        "under_review": "order.payment_under_review",
        "paid": "order.payment_paid",
    }
    status = t(status_labels.get(order.status.value, "order.status"), language=language)
    payment_status = t(payment_labels.get(order.payment_status, "order.payment_status"), language=language)
    expires = order.expires_at.strftime("%Y-%m-%d %H:%M UTC") if order.expires_at else "—"
    return "\n".join([
        t(title_key, language=language), "",
        f"{t('order.number', language=language)}: #{order.public_order_id}",
        f"{t('package.name', language=language)}: {snapshot.name}",
        f"{t('package.data', language=language)}: {data}",
        f"{t('package.duration', language=language)}: {snapshot.duration_days} {t('package.days', language=language)}",
        f"{t('package.devices', language=language)}: {devices}",
        f"{t('package.price', language=language)}: {_money(order.total_amount, order.currency)}",
        f"{t('order.status', language=language)}: {status}",
        f"{t('order.payment_status', language=language)}: {payment_status}",
        f"Payment method: {method}",
        f"Expires: {expires}",
    ])


def _wallet_preview_text(preview, language: str) -> str:
    return "\n".join([
        t("order.wallet_preview_title", language=language), "",
        f"{t('order.number', language=language)}: #{preview.public_order_id}",
        f"{t('package.name', language=language)}: {preview.package_name}",
        f"{t('order.order_amount', language=language)}: {_money(preview.amount, preview.currency)}",
        f"{t('order.wallet_balance', language=language)}: {_money(preview.wallet_balance, preview.currency)}",
        f"{t('order.balance_after', language=language)}: {_money(preview.balance_after, preview.currency)}",
        "",
        t("order.wallet_confirm", language=language),
    ])


def _wallet_failure_text(result, language: str) -> str:
    error = result.error
    code = error.code if error is not None else "payment_failed"
    messages = {
        "insufficient_balance": "order.insufficient_balance",
        "wallet_not_found": "order.invalid_wallet",
        "wallet_frozen": "order.wallet_disabled",
        "currency_mismatch": "order.currency_mismatch",
        "already_paid": "order.already_paid",
        "order_expired": "order.expired",
        "balance_changed": "order.balance_changed",
    }
    text = t(messages.get(code, "order.payment_failed"), language=language)
    if error is not None and error.details and code == "insufficient_balance":
        needed = error.details.get("needed")
        currency = error.details.get("currency", "")
        if needed:
            text += f"\n{t('order.amount_needed', language=language)}: {needed} {currency}"
    if code not in {"already_paid", "order_expired"}:
        text += f"\n\n{t('order.wallet_not_charged', language=language)}"
    return text


def _labels() -> set[str]:
    return {t("menu.buy_vpn", language=lang) for lang in ("en", "my")}


_LABELS = _labels()
_PATTERN = r"^(?:" + "|".join(re.escape(x) for x in _LABELS) + r")$"


@log_handler
async def buy_vpn_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show_catalog(update, context, 1)


@log_handler
async def package_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query; user = _get_user(context)
    if q is None or not _is_customer_surface(user):
        return
    await q.answer()
    lang = _language(user)
    data = q.data or ""
    svc = _service(context)
    callback_security = _callback_service(context)
    if svc is None:
        if q.message: await q.message.reply_text(t("common.error", language=lang))
        return

    try:
        if data.startswith("pkg:list:"):
            page = max(1, int(data.rsplit(":", 1)[1]))
            await _show_catalog(update, context, page)
            return

        if data.startswith("pkg:view:"):
            package_id = int(data.rsplit(":", 1)[1])
            if package_id <= 0: raise ValueError
            await _show_details(update, context, package_id)
            return

        if data.startswith("pkg:select:"):
            package_id = int(data.rsplit(":", 1)[1])
            if package_id <= 0: raise ValueError
            selection = await svc.prepare_purchase_handoff(user.telegram_id, package_id)
            if selection is None:
                if q.message: await q.message.reply_text(t("package.unavailable", language=lang))
                return
            context.user_data[_SELECTION_KEY] = selection
            if q.message:
                await q.message.reply_text(
                    "\n".join([
                        t("package.selected_title", language=lang), "",
                        f"{t('package.name', language=lang)}: {selection.package_name}",
                        f"{t('package.price', language=lang)}: {_money(selection.quoted_price, selection.currency)}",
                        "",
                        t("package.payment_handoff", language=lang),
                    ]),
                    reply_markup=build_package_selected_keyboard(selection.package_id, lang),
                )
            return

        if data == "pkg:checkout":
            selection = context.user_data.get(_SELECTION_KEY)
            checkout = _checkout_service(context)
            if not isinstance(selection, PackageSelection) or checkout is None:
                if q.message: await q.message.reply_text(t("package.selection_expired", language=lang))
                return
            try:
                await checkout.prepare_checkout(selection)
            except CheckoutExpiredError:
                context.user_data.pop(_SELECTION_KEY, None)
                if q.message: await q.message.reply_text(t("order.checkout_expired", language=lang))
                return
            except PackageChangedError:
                if q.message: await q.message.reply_text(t("order.checkout_changed", language=lang))
                return
            confirm_data = cancel_data = None
            if callback_security is not None:
                confirm_ref = await callback_security.issue(
                    action_type="checkout.confirm",
                    actor_user_id=user.id,
                    actor_telegram_id=user.telegram_id,
                    chat_id=update.effective_chat.id if update.effective_chat else None,
                    chat_type=update.effective_chat.type if update.effective_chat else None,
                    resource_type="checkout",
                    resource_public_id=selection.checkout_token,
                    state_version=selection.expires_at.isoformat(),
                    safe_metadata={"surface": "package_checkout"},
                )
                cancel_ref = await callback_security.issue(
                    action_type="checkout.cancel",
                    actor_user_id=user.id,
                    actor_telegram_id=user.telegram_id,
                    chat_id=update.effective_chat.id if update.effective_chat else None,
                    chat_type=update.effective_chat.type if update.effective_chat else None,
                    resource_type="checkout",
                    resource_public_id=selection.checkout_token,
                    state_version=selection.expires_at.isoformat(),
                    safe_metadata={"surface": "package_checkout"},
                )
                if confirm_ref.is_success:
                    confirm_data = confirm_ref.unwrap().data
                if cancel_ref.is_success:
                    cancel_data = cancel_ref.unwrap().data
            if q.message:
                await q.message.reply_text(
                    _checkout_text(selection, lang),
                    reply_markup=build_checkout_keyboard(selection.checkout_token, lang, confirm_data, cancel_data),
                )
            return
    except (TypeError, ValueError):
        logger.info("Malformed package callback: %r", data)
        if q.message:
            await q.message.reply_text(t("package.invalid_callback", language=lang))


async def manual_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    user = _get_user(context)
    if q is None or not _is_customer_surface(user):
        return
    await q.answer()
    lang = _language(user)
    parts = (q.data or "").split(":")
    if len(parts) != 4 or parts[0] != "manual" or parts[1] not in {"method", "submit"} or not parts[3].startswith("ORD-"):
        if q.message:
            await q.message.reply_text(t("order.invalid_callback", language=lang))
        return
    method_id, public_id = parts[2], parts[3]
    order_service = _order_service(context)
    manual_service = _manual_payment_service(context)
    if order_service is None or manual_service is None or q.message is None:
        return
    try:
        order = await order_service.get_customer_order(user.telegram_id, public_id)
        method = await manual_service.get_method(method_id, amount=order.total_amount, currency=order.currency)
        if method is None:
            await q.message.reply_text(t("order.manual_not_configured", language=lang))
            return
        if parts[1] == "method":
            await q.message.reply_text(
                _manual_method_text(method, order, lang),
                reply_markup=build_manual_payment_instruction_keyboard(public_id, method.method_id, lang),
            )
            return
        context.user_data[_MANUAL_PAYMENT_KEY] = {
            "order_id": public_id,
            "method_id": method.method_id,
            "stage": "reference",
        }
        await q.message.reply_text(
            t("order.manual_reference_prompt", language=lang, order=public_id),
            reply_markup=ForceReply(selective=True),
        )
    except (OrderNotFoundError, CustomerRestrictedError):
        await q.message.reply_text(t("order.not_found", language=lang))
    except InvalidOrderStateError:
        await q.message.reply_text(t("order.invalid_state", language=lang))
    except (TypeError, ValueError):
        await q.message.reply_text(t("order.invalid_callback", language=lang))


async def manual_reference_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _get_user(context)
    message = update.effective_message
    state = context.user_data.get(_MANUAL_PAYMENT_KEY)
    if not _is_customer_surface(user) or message is None or not isinstance(state, dict) or state.get("stage") != "reference":
        return
    reference = (message.text or "").strip()
    lang = _language(user)
    if not reference or len(reference) > 256:
        await message.reply_text(t("order.manual_reference_prompt", language=lang, order=state.get("order_id", "")), reply_markup=ForceReply(selective=True))
        return
    state["reference"] = reference
    state["stage"] = "proof"
    await message.reply_text(
        t("order.manual_reference_saved", language=lang, order=state["order_id"]),
    )


async def manual_proof_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _get_user(context)
    message = update.effective_message
    state = context.user_data.get(_MANUAL_PAYMENT_KEY)
    if not _is_customer_surface(user) or message is None or not isinstance(state, dict) or state.get("stage") != "proof":
        return
    lang = _language(user)
    proof_file_id = None
    proof_unique_id = None
    proof_type = None
    if message.photo:
        photo = message.photo[-1]
        proof_file_id = photo.file_id
        proof_unique_id = photo.file_unique_id
        proof_type = "photo"
    elif message.document:
        proof_file_id = message.document.file_id
        proof_unique_id = message.document.file_unique_id
        proof_type = message.document.mime_type or "document"
    else:
        await message.reply_text(t("order.manual_proof_required", language=lang))
        return
    service = _payment_submission_service(context)
    if service is None:
        await message.reply_text(t("common.error", language=lang))
        return
    result = await service.submit(
        user_id=user.telegram_id,
        public_order_id=state["order_id"],
        method_id=state["method_id"],
        transaction_reference=state.get("reference"),
        proof_file_id=proof_file_id,
        proof_file_unique_id=proof_unique_id,
        proof_file_type=proof_type,
    )
    if result.is_success:
        receipt = result.unwrap()
        context.user_data.pop(_MANUAL_PAYMENT_KEY, None)
        await message.reply_text(
            t("order.manual_waiting_review", language=lang, order=receipt.public_order_id),
            reply_markup=build_manual_payment_waiting_keyboard(receipt.public_order_id, lang),
        )
        return
    error_code = result.error.code if result.error is not None else ""
    error_key = {
        "proof_required": "order.manual_proof_required",
        "review_pending": "order.manual_duplicate",
        "manual_method_unavailable": "order.manual_not_configured",
        "already_paid": "order.already_paid",
        "order_expired": "order.expired",
        "order_not_found": "order.not_found",
    }.get(error_code, "common.error")
    await message.reply_text(t(error_key, language=lang))


async def order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle checkout confirmation and ownership-safe order callbacks."""
    q = update.callback_query
    user = _get_user(context)
    if q is None or not _is_customer_surface(user):
        return
    await q.answer()
    lang = _language(user)
    data = q.data or ""
    order_service = _order_service(context)
    checkout = _checkout_service(context)
    callback_security = _callback_service(context)
    if order_service is None or checkout is None:
        if q.message: await q.message.reply_text(t("order.generic_error", language=lang))
        return

    try:
        if data.startswith("cb2:"):
            if callback_security is None:
                if q.message: await q.message.reply_text(t("order.invalid_callback", language=lang))
                return
            action_type = await callback_security.action_type_for(data)
            allowed = {"checkout.confirm", "checkout.cancel", "wallet.pay", "order.cancel"}
            if action_type not in allowed:
                return
            platform_user = context.user_data.get(PLATFORM_USER_KEY)
            actor_user_id = getattr(platform_user, "id", None)
            if actor_user_id is None:
                if q.message: await q.message.reply_text(t("order.invalid_callback", language=lang))
                return
            consumed = await callback_security.consume(
                callback_data=data,
                action_type=action_type,
                actor_user_id=actor_user_id,
                actor_telegram_id=user.telegram_id,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                chat_type=update.effective_chat.type if update.effective_chat else None,
                request_id=(context.user_data.get("request_context").request_id if context.user_data.get("request_context") else None),
            )
            if not consumed.is_success:
                if q.message: await q.message.reply_text(t("order.invalid_callback", language=lang))
                return
            action = consumed.unwrap()
            if action_type in {"checkout.confirm", "checkout.cancel"}:
                selection = context.user_data.get(_SELECTION_KEY)
                if not isinstance(selection, PackageSelection) or action.resource_public_id != selection.checkout_token:
                    if q.message: await q.message.reply_text(t("order.checkout_expired", language=lang))
                    return
                if action_type == "checkout.cancel":
                    context.user_data.pop(_SELECTION_KEY, None)
                    if q.message: await q.message.reply_text(t("package.selection_expired", language=lang))
                    return
                order = await checkout.create_order(selection)
                context.user_data.pop(_SELECTION_KEY, None)
                if q.message:
                    await q.message.reply_text(_order_text(order, lang), reply_markup=build_order_created_keyboard(order.public_order_id, lang))
                return
            public_id = action.resource_public_id
            if not public_id:
                if q.message: await q.message.reply_text(t("order.invalid_callback", language=lang))
                return
            if action_type == "wallet.pay":
                wallet_service = _wallet_payment_service(context)
                if wallet_service is None:
                    if q.message: await q.message.reply_text(t("order.payment_failed", language=lang))
                    return
                payment = await wallet_service.pay(user_id=user.telegram_id, public_order_id=public_id)
                if q.message:
                    await q.message.reply_text(_wallet_failure_text(payment, lang) if not payment.is_success else t("order.payment_successful", language=lang), reply_markup=build_wallet_payment_result_keyboard(lang) if payment.is_success else build_order_details_keyboard(public_id, lang))
                return
            order = await order_service.cancel_order(user.telegram_id, public_id)
            if q.message:
                await q.message.reply_text(_order_text(order, lang, "order.cancelled") + "\\n\\n" + t("order.no_charge", language=lang), reply_markup=build_cancelled_keyboard(lang))
            return

        if data.startswith("checkout:"):
            action, token = data.split(":", 2)[1:]
            selection = context.user_data.get(_SELECTION_KEY)
            if not isinstance(selection, PackageSelection) or selection.checkout_token != token:
                if q.message: await q.message.reply_text(t("order.checkout_expired", language=lang))
                return
            if action == "cancel":
                context.user_data.pop(_SELECTION_KEY, None)
                if q.message: await q.message.reply_text(t("package.selection_expired", language=lang))
                return
            if action != "confirm":
                raise ValueError("invalid checkout action")
            order = await checkout.create_order(selection)
            context.user_data.pop(_SELECTION_KEY, None)
            if q.message:
                await q.message.reply_text(
                    _order_text(order, lang),
                    reply_markup=build_order_created_keyboard(order.public_order_id, lang),
                )
            return

        if not data.startswith("order:"):
            return
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        public_id = parts[-1] if len(parts) > 2 else ""
        if not public_id.startswith("ORD-"):
            raise ValueError("invalid public order id")

        if action == "view":
            order = await order_service.get_customer_order(user.telegram_id, public_id)
            if q.message:
                await q.message.reply_text(
                    _order_text(order, lang, "order.created"),
                    reply_markup=build_order_details_keyboard(public_id, lang),
                )
            return

        if action == "pay" and len(parts) == 3:
            order = await order_service.get_customer_order(user.telegram_id, public_id)
            if q.message:
                await q.message.reply_text(
                    _order_text(order, lang),
                    reply_markup=build_payment_methods_keyboard(public_id, lang),
                )
            return

        if action == "pay" and len(parts) == 4:
            order = await order_service.get_customer_order(user.telegram_id, public_id)
            if parts[2] == "manual":
                manual_service = _manual_payment_service(context)
                methods = [] if manual_service is None else await manual_service.list_enabled_methods(
                    amount=order.total_amount,
                    currency=order.currency,
                )
                if q.message:
                    if not methods:
                        await q.message.reply_text(
                            t("order.manual_not_configured", language=lang),
                            reply_markup=build_order_details_keyboard(public_id, lang),
                        )
                    else:
                        await q.message.reply_text(
                            t("order.manual_methods_title", language=lang),
                            reply_markup=build_manual_payment_methods_keyboard(public_id, methods, lang),
                        )
                return
            if parts[2] == "wallet":
                wallet_service = _wallet_payment_service(context)
                if wallet_service is None:
                    if q.message: await q.message.reply_text(t("order.payment_failed", language=lang))
                    return
                preview = await wallet_service.preview(
                    user_id=user.telegram_id,
                    public_order_id=public_id,
                )
                if q.message:
                    if preview.is_success:
                        confirm_data = None
                        if callback_security is not None:
                            issued = await callback_security.issue(
                                action_type="wallet.pay",
                                actor_user_id=user.id,
                                actor_telegram_id=user.telegram_id,
                                chat_id=update.effective_chat.id if update.effective_chat else None,
                                chat_type=update.effective_chat.type if update.effective_chat else None,
                                resource_type="order",
                                resource_public_id=public_id,
                                safe_metadata={"surface": "wallet_payment"},
                            )
                            if issued.is_success:
                                confirm_data = issued.unwrap().data
                        await q.message.reply_text(
                            _wallet_preview_text(preview.unwrap(), lang),
                            reply_markup=build_wallet_payment_preview_keyboard(public_id, lang, confirm_data),
                        )
                    else:
                        await q.message.reply_text(
                            _wallet_failure_text(preview, lang),
                            reply_markup=build_order_details_keyboard(public_id, lang),
                        )
                return
            if q.message:
                await q.message.reply_text(
                    _order_text(order, lang) + "\n\n" + t("order.manual_placeholder", language=lang),
                    reply_markup=build_order_details_keyboard(public_id, lang),
                )
            return

        if data.startswith("wallet:"):
            if len(parts) != 3:
                raise ValueError("invalid wallet callback")
            wallet_action, wallet_public_id = parts[1], parts[2]
            if not wallet_public_id.startswith("ORD-"):
                raise ValueError("invalid public order id")
            wallet_service = _wallet_payment_service(context)
            if wallet_service is None:
                if q.message: await q.message.reply_text(t("order.payment_failed", language=lang))
                return
            if wallet_action == "cancel":
                order = await order_service.get_customer_order(user.telegram_id, wallet_public_id)
                if q.message:
                    await q.message.reply_text(
                        _order_text(order, lang),
                        reply_markup=build_payment_methods_keyboard(wallet_public_id, lang),
                    )
                return
            if wallet_action != "confirm":
                raise ValueError("invalid wallet action")
            payment = await wallet_service.pay(
                user_id=user.telegram_id,
                public_order_id=wallet_public_id,
            )
            if q.message:
                if payment.is_success:
                    receipt = payment.unwrap()
                    title = "order.already_paid" if receipt.already_processed else "order.payment_successful"
                    success_text = "\n".join([
                        t(title, language=lang),
                        f"{t('order.number', language=lang)}: #{receipt.public_order_id}",
                        f"{t('order.order_amount', language=lang)}: {_money(receipt.amount, receipt.currency)}",
                        f"{t('order.balance_after', language=lang)}: {_money(receipt.remaining_balance, receipt.currency)}",
                        f"{t('order.payment_reference', language=lang)}: {receipt.payment_reference}",
                    ])
                    await q.message.reply_text(
                        success_text,
                        reply_markup=build_wallet_payment_result_keyboard(lang),
                    )
                else:
                    await q.message.reply_text(
                        _wallet_failure_text(payment, lang),
                        reply_markup=build_order_details_keyboard(wallet_public_id, lang),
                    )
            return

        if action == "cancel" and len(parts) == 3:
            order = await order_service.get_customer_order(user.telegram_id, public_id)
            if not order.is_cancellable:
                if q.message: await q.message.reply_text(t("order.invalid_state", language=lang))
                return
            if q.message:
                confirm_data = None
                if callback_security is not None:
                    issued = await callback_security.issue(
                        action_type="order.cancel",
                        actor_user_id=user.id,
                        actor_telegram_id=user.telegram_id,
                        chat_id=update.effective_chat.id if update.effective_chat else None,
                        chat_type=update.effective_chat.type if update.effective_chat else None,
                        resource_type="order",
                        resource_public_id=public_id,
                        safe_metadata={"surface": "order_cancel"},
                    )
                    if issued.is_success:
                        confirm_data = issued.unwrap().data
                await q.message.reply_text(
                    _order_text(order, lang) + "\n\n" + t("order.cancel_confirm_prompt", language=lang),
                    reply_markup=build_cancel_confirmation_keyboard(public_id, lang, confirm_data),
                )
            return

        if action == "cancel_confirm" and len(parts) == 3:
            order = await order_service.cancel_order(user.telegram_id, public_id)
            if q.message:
                await q.message.reply_text(
                    _order_text(order, lang, "order.cancelled") + "\n\n" + t("order.no_charge", language=lang),
                    reply_markup=build_cancelled_keyboard(lang),
                )
            return

        if action == "cancel_keep" and len(parts) == 3:
            order = await order_service.get_customer_order(user.telegram_id, public_id)
            if q.message:
                await q.message.reply_text(
                    _order_text(order, lang),
                    reply_markup=build_order_details_keyboard(public_id, lang),
                )
            return

        raise ValueError("invalid order callback")
    except (CheckoutExpiredError, PackageChangedError):
        context.user_data.pop(_SELECTION_KEY, None)
        if q.message: await q.message.reply_text(t("order.checkout_expired", language=lang))
    except (OrderNotFoundError, CustomerRestrictedError):
        # Intentionally do not reveal whether another user's order exists.
        if q.message: await q.message.reply_text(t("order.not_found", language=lang))
    except InvalidOrderStateError:
        if q.message: await q.message.reply_text(t("order.invalid_state", language=lang))
    except (TypeError, ValueError):
        logger.info("Malformed order callback: %r", data)
        if q.message: await q.message.reply_text(t("order.invalid_callback", language=lang))


def register(application: Application) -> None:
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(_PATTERN), buy_vpn_message),
        group=8,
    )
    application.add_handler(
        CallbackQueryHandler(package_callback, pattern=r"^pkg:(?:list:\d+|view:\d+|select:\d+|checkout)$"),
        group=8,
    )
    application.add_handler(
        CallbackQueryHandler(
            manual_payment_callback,
            pattern=r"^manual:(?:method|submit):[^:]+:ORD-[^:]+$",
        ),
        group=8,
    )
    application.add_handler(
        MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, manual_reference_message),
        group=8,
    )
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, manual_proof_message),
        group=8,
    )
    application.add_handler(
        CallbackQueryHandler(
            order_callback,
            pattern=r"^(?:checkout:(?:confirm|cancel):[^:]+|order:(?:view|pay|cancel|cancel_confirm|cancel_keep):.+|order:pay:(?:wallet|manual):.+|wallet:(?:confirm|cancel):ORD-[^:]+)$",
        ),
        group=8,
    )
    application.add_handler(CallbackQueryHandler(order_callback, pattern=r"^cb2:"), group=8)
    logger.debug("Phase 1.4 package catalogue handlers registered")
