"""Telegram admin UI for API URL and existing-VPS SSH Outline setup."""

from __future__ import annotations

from telegram import ForceReply, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.handlers.base import permission_required
from app.keyboards.admin_outline_setup import outline_not_found_keyboard, outline_review_keyboard, outline_setup_methods_keyboard, provisioning_confirm_keyboard, ssh_auth_keyboard, ssh_test_keyboard
from app.models.outline_setup import OutlineCredentialInput, OutlineSetupReview
from app.models.ssh_discovery import OutlineSSHDiscoveryResult
from app.services.callback_security_service import CallbackSecurityService
from app.services.outline_setup_service import OutlineSetupService
from app.services.outline_provisioning_service import OutlineProvisioningService
from app.services.ssh_discovery_service import SSHDiscoveryService
from app.middlewares.auth import PLATFORM_USER_KEY
from locales.translator import t

_STATE = "phase32_outline_setup"


def _language(context) -> str:
    user = context.user_data.get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", None) or getattr(user, "language", None)
    return value if value in {"en", "my"} else "en"


def _actor(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def _service(context) -> OutlineSetupService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(OutlineSetupService)


def _provisioning_service(context) -> OutlineProvisioningService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(OutlineProvisioningService)


def _ssh_service(context) -> SSHDiscoveryService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(SSHDiscoveryService)


def _callback_service(context) -> CallbackSecurityService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(CallbackSecurityService)


async def _secure_flow_callbacks(update, context, actor: int, flow_id: str, actions: tuple[str, ...]) -> dict[str, str]:
    service = _callback_service(context)
    callbacks: dict[str, str] = {}
    if service is None:
        return callbacks
    for action in actions:
        issued = await service.issue(
            action_type=f"admin.outline.{action}", actor_user_id=actor, actor_telegram_id=actor,
            chat_id=update.effective_chat.id if update.effective_chat else None,
            chat_type=update.effective_chat.type if update.effective_chat else None,
            resource_type="outline_flow", resource_public_id=str(flow_id),
            safe_metadata={"action": action},
        )
        if issued.is_success:
            callbacks[action] = issued.unwrap().data
    return callbacks


def _plan_text(plan, language: str) -> str:
    p = plan.preflight
    return t("admin.outline.provision_plan", language=language, host=plan.host, os=p.os_name or "—", arch=p.architecture or "—", privilege=p.privilege_mode, disk=p.disk_free_mb or "—", memory=p.memory_available_mb or "—", docker="✅" if p.docker_available else "❌", changes="; ".join(plan.expected_changes), warnings="; ".join(plan.warnings) or "—")


def _review_text(review: OutlineSetupReview, language: str, *, ssh: OutlineSSHDiscoveryResult | None = None) -> str:
    d = review.discovery; prefix = "🖥 VPS / SSH\n" if ssh else ""
    host_line = f"\nVPS Host: {ssh.host}\nOS: {ssh.os_name or '—'}\nSSH: ✅ Connected" if ssh else ""
    return prefix + t("admin.outline.review", language=language, public_id=review.server_public_id or "new", name=review.name or "—", location=" / ".join(x for x in (review.country_code, review.region) if x) or "—", provider="Outline", method=review.source, connection="✅ Verified" + host_line, api="✅ Compatible" if d.api_compatible else "❌ Incompatible", version=d.outline_version or "—", keys=d.existing_key_count if d.existing_key_count is not None else "—", credential="🔐 Ready for secure storage", paid="✅" if review.paid_enabled else "❌", free_trial="✅" if review.free_trial_enabled else "❌", vip="✅" if review.vip_enabled else "❌", max_users=review.max_users or "∞", status="Verified / Disabled until explicitly enabled")


async def _start_metadata(message, context, flow_id: str, review: OutlineSetupReview, language: str, *, ssh: OutlineSSHDiscoveryResult | None = None) -> None:
    context.user_data[_STATE] = {"flow_id": flow_id, "stage": "name", "actor": context.user_data[_STATE].get("actor"), "review": review, "ssh_discovery": ssh}
    await message.reply_text(t("admin.outline.metadata_name", language=language), reply_markup=ForceReply(selective=True))


@permission_required("manage_servers")
async def outline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; message = update.effective_message; actor = _actor(update); language = _language(context); service = _service(context); ssh_service = _ssh_service(context)
    if query is None or message is None or actor is None: return
    await query.answer()
    if service is None: await message.reply_text(t("common.error", language=language)); return
    raw_data = query.data or ""
    parts = raw_data.split(":")
    callback_security = _callback_service(context)
    if raw_data.startswith("cb2:"):
        action_type = None if callback_security is None else await callback_security.action_type_for(raw_data)
        if not action_type or not action_type.startswith("admin.outline."):
            return
        consumed = await callback_security.consume(
            callback_data=raw_data, action_type=action_type, actor_user_id=actor, actor_telegram_id=actor,
            chat_id=update.effective_chat.id if update.effective_chat else None,
            chat_type=update.effective_chat.type if update.effective_chat else None,
            expected_resource_type="outline_flow",
        )
        if not consumed.is_success:
            await message.reply_text(t("admin.outline.expired", language=language)); return
        payload = consumed.unwrap()
        flow_id = payload.resource_public_id
        action = str(payload.safe_metadata.get("action") or action_type.removeprefix("admin.outline."))
        if not flow_id or action not in {"auto_confirm", "cancel", "save_disabled", "save_enable", "test_again", "ssh_test"}:
            await message.reply_text(t("admin.outline.expired", language=language)); return
        parts = ["admin", "outline", action, flow_id]
    if parts == ["admin", "outline", "api_url"]:
        result = await service.start_setup(admin_id=actor, setup_method="api_url")
        if not result.is_success: await message.reply_text(t("admin.outline.error", language=language)); return
        flow = result.unwrap(); context.user_data[_STATE] = {"flow_id": flow.flow_id, "stage": "api_credential", "actor": actor, "mode": "api"}
        await message.reply_text(t("admin.outline.api_prompt", language=language), reply_markup=ForceReply(selective=True)); return
    if parts == ["admin", "outline", "future", "auto"]:
        if ssh_service is None or _provisioning_service(context) is None: await message.reply_text(t("admin.outline.error", language=language)); return
        result = await ssh_service.start_setup(admin_id=actor)
        if not result.is_success: await message.reply_text(t("admin.outline.error", language=language)); return
        flow_id = result.unwrap(); context.user_data[_STATE] = {"flow_id": flow_id, "ssh_flow_id": flow_id, "stage": "ssh_host", "actor": actor, "mode": "auto"}
        await message.reply_text(t("admin.outline.auto_ssh_host", language=language), reply_markup=ForceReply(selective=True)); return
    if len(parts) == 5 and parts[:3] == ["admin", "outline", "auto_confirm"]:
        flow_id, token = parts[3], parts[4]; state = context.user_data.get(_STATE) or {}; provisioning = _provisioning_service(context)
        if provisioning is None or state.get("actor") != actor or state.get("flow_id") != flow_id:
            await message.reply_text(t("admin.outline.expired", language=language)); return
        confirmation = provisioning.confirm(admin_id=actor, flow_id=flow_id, token=token)
        if not confirmation.is_success:
            await message.reply_text(t("admin.outline.provision_confirm_required", language=language)); return
        await query.edit_message_text(t("admin.outline.provision_installing", language=language))
        result = await provisioning.install(admin_id=actor, flow_id=flow_id)
        if not result.is_success:
            await message.reply_text(t("admin.outline.provision_failed", language=language)); return
        state["stage"] = "name"; state["review"] = result.unwrap()
        await message.reply_text(t("admin.outline.metadata_name", language=language), reply_markup=ForceReply(selective=True)); return
    if parts == ["admin", "outline", "future", "ssh"]:
        if ssh_service is None: await message.reply_text(t("admin.outline.error", language=language)); return
        result = await ssh_service.start_setup(admin_id=actor)
        if not result.is_success: await message.reply_text(t("admin.outline.error", language=language)); return
        flow_id = result.unwrap(); context.user_data[_STATE] = {"flow_id": flow_id, "stage": "ssh_host", "actor": actor, "mode": "ssh"}
        await message.reply_text(t("admin.outline.ssh_host", language=language), reply_markup=ForceReply(selective=True)); return
    if len(parts) == 5 and parts[:3] == ["admin", "outline", "ssh_auth"]:
        flow_id, method = parts[4], parts[3]; state = context.user_data.get(_STATE) or {}
        if ssh_service is None or state.get("actor") != actor or state.get("flow_id") != flow_id: await message.reply_text(t("admin.outline.expired", language=language)); return
        state["stage"] = "ssh_secret"; state["auth_method"] = method
        await message.reply_text(t("admin.outline.ssh_password_prompt" if method == "password" else "admin.outline.ssh_key_prompt", language=language), reply_markup=ForceReply(selective=True)); return
    if len(parts) == 4 and parts[:3] == ["admin", "outline", "ssh_test"]:
        flow_id = parts[3]; state = context.user_data.get(_STATE) or {}
        if ssh_service is None or state.get("actor") != actor or state.get("flow_id") != flow_id: await message.reply_text(t("admin.outline.expired", language=language)); return
        result = await ssh_service.discover_stored(admin_id=actor, flow_id=flow_id)
        if result.is_success:
            value = result.unwrap()
            if isinstance(value, OutlineSSHDiscoveryResult) and not value.outline_found:
                context.user_data.pop(_STATE, None); await message.reply_text(t("admin.outline.ssh_not_found", language=language), reply_markup=outline_not_found_keyboard(language)); return
            context.user_data[_STATE]["stage"] = "name"
            context.user_data[_STATE]["review"] = value.outline_review
            context.user_data[_STATE]["ssh_discovery"] = value.discovery
            await message.reply_text(t("admin.outline.metadata_name", language=language), reply_markup=ForceReply(selective=True)); return
        await message.reply_text(t("admin.outline.ssh_failed", language=language)); return
    if len(parts) == 4 and parts[2] == "future":
        await message.reply_text(t("admin.outline.coming_soon", language=language, feature="SSH"), reply_markup=outline_setup_methods_keyboard(language)); return
    if len(parts) == 4 and parts[2] in {"cancel", "test_again", "save_disabled", "save_enable"}:
        flow_id = parts[3]; state = context.user_data.get(_STATE) or {}
        if state.get("actor") != actor or state.get("flow_id") != flow_id: await message.reply_text(t("admin.outline.expired", language=language)); return
        if parts[2] == "cancel":
            provisioning = _provisioning_service(context)
            if state.get("mode") == "auto" and provisioning:
                provisioning.cancel(admin_id=actor, flow_id=flow_id)
                if ssh_service and state.get("ssh_flow_id"): ssh_service.cancel(admin_id=actor, flow_id=state["ssh_flow_id"])
            else:
                if ssh_service: ssh_service.cancel(admin_id=actor, flow_id=flow_id)
                service.cancel_setup(admin_id=actor, flow_id=flow_id)
            context.user_data.pop(_STATE, None); await message.reply_text(t("admin.outline.cancelled", language=language), reply_markup=outline_setup_methods_keyboard(language)); return
        if parts[2] == "test_again":
            result = await service.reverify(admin_id=actor, flow_id=flow_id)
            if result.is_success:
                callbacks = await _secure_flow_callbacks(update, context, actor, flow_id, ("save_disabled", "save_enable", "test_again", "cancel"))
                await message.reply_text(_review_text(result.unwrap(), language, ssh=state.get("ssh_discovery")), reply_markup=outline_review_keyboard(language, flow_id, callbacks))
            else: await message.reply_text(t("admin.outline.error", language=language)); return
        meta = state.get("metadata") or {}; result = await service.save_verified(admin_id=actor, flow_id=flow_id, name=meta.get("name", "Outline Server"), country_code=meta.get("country_code"), region=meta.get("region"), enable=parts[2] == "save_enable")
        context.user_data.pop(_STATE, None)
        if result.is_success:
            saved = result.unwrap(); await message.reply_text(t("admin.outline.saved", language=language, public_id=saved.server_public_id, status=saved.status, enabled="✅" if saved.enabled else "❌"))
        else: await message.reply_text(t("admin.outline.error", language=language))


@permission_required("manage_servers")
async def outline_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message; actor = _actor(update); state = context.user_data.get(_STATE) or {}; language = _language(context); service = _service(context); ssh_service = _ssh_service(context)
    if message is None or actor is None or state.get("actor") != actor: return
    text = (message.text or "").strip(); stage = state.get("stage"); flow_id = state.get("flow_id")
    if stage == "api_credential" and service:
        result = await service.validate_and_verify(admin_id=actor, flow_id=flow_id, credential=OutlineCredentialInput(management_url=text, source="api_url"))
        if not result.is_success: await message.reply_text(t("admin.outline.verify_failed", language=language), reply_markup=outline_setup_methods_keyboard(language)); return
        state["stage"] = "name"; state["review"] = result.unwrap(); await message.reply_text(t("admin.outline.metadata_name", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "ssh_host" and ssh_service:
        state["host"] = text; state["stage"] = "ssh_port"; await message.reply_text(t("admin.outline.ssh_port", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "ssh_port" and ssh_service:
        try: port = int(text)
        except ValueError: await message.reply_text(t("admin.outline.ssh_invalid", language=language)); return
        state["port"] = port; state["stage"] = "ssh_username"; await message.reply_text(t("admin.outline.ssh_username", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "ssh_username" and ssh_service:
        prepared = ssh_service.set_connection_details(admin_id=actor, flow_id=flow_id, host=state["host"], port=state["port"], username=text)
        if not prepared.is_success: await message.reply_text(t("admin.outline.ssh_invalid", language=language)); return
        state["stage"] = "ssh_auth"; await message.reply_text(t("admin.outline.ssh_auth_method", language=language), reply_markup=ssh_auth_keyboard(language, flow_id)); return
    if stage == "ssh_secret" and ssh_service:
        stored = ssh_service.set_auth_secret(admin_id=actor, flow_id=flow_id, auth_method=state["auth_method"], secret=text)
        if not stored.is_success: await message.reply_text(t("admin.outline.ssh_invalid", language=language)); return
        state["stage"] = "ssh_fingerprint"; await message.reply_text(t("admin.outline.ssh_fingerprint", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "ssh_fingerprint" and ssh_service:
        stored = ssh_service.set_host_key_fingerprint(admin_id=actor, flow_id=flow_id, fingerprint=text)
        if not stored.is_success: await message.reply_text(t("admin.outline.ssh_invalid", language=language)); return
        if state.get("mode") == "auto":
            built = ssh_service.build_credential(admin_id=actor, flow_id=flow_id)
            provisioning = _provisioning_service(context)
            if not built.is_success or provisioning is None:
                await message.reply_text(t("admin.outline.ssh_failed", language=language)); return
            started = await provisioning.start(admin_id=actor, credential=built.unwrap())
            if not started.is_success:
                await message.reply_text(t("admin.outline.ssh_failed", language=language)); return
            provisioning_flow = started.unwrap().flow_id
            state["ssh_flow_id"] = flow_id; state["flow_id"] = provisioning_flow; state["stage"] = "provisioning"
            ssh_service.cancel(admin_id=actor, flow_id=flow_id)
            preflight = await provisioning.preflight(admin_id=actor, flow_id=provisioning_flow)
            if not preflight.is_success:
                await message.reply_text(t("admin.outline.provision_failed", language=language)); return
            value = preflight.unwrap()
            if hasattr(value, "preflight"):
                token = provisioning.confirmation_token(admin_id=actor, flow_id=provisioning_flow) or ""
                callbacks = await _secure_flow_callbacks(update, context, actor, provisioning_flow, ("auto_confirm", "cancel"))
                await message.reply_text(_plan_text(value, language), reply_markup=provisioning_confirm_keyboard(language, provisioning_flow, token, callbacks)); return
            state["stage"] = "name"; state["review"] = value
            await message.reply_text(t("admin.outline.metadata_name", language=language), reply_markup=ForceReply(selective=True)); return
        state["stage"] = "ssh_test"; callbacks = await _secure_flow_callbacks(update, context, actor, flow_id, ("ssh_test", "cancel")); await message.reply_text(t("admin.outline.ssh_ready", language=language), reply_markup=ssh_test_keyboard(language, flow_id, callbacks)); return
    if stage == "name":
        state.setdefault("metadata", {})["name"] = text; state["stage"] = "country"; await message.reply_text(t("admin.outline.metadata_country", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "country":
        state.setdefault("metadata", {})["country_code"] = None if text in {"—", "-"} else text; state["stage"] = "region"; await message.reply_text(t("admin.outline.metadata_region", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "region":
        state.setdefault("metadata", {})["region"] = None if text in {"—", "-"} else text; state["stage"] = "review"; review: OutlineSetupReview = state["review"]; meta = state["metadata"]
        review = OutlineSetupReview(flow_id=review.flow_id, server_public_id=review.server_public_id, source=review.source, discovery=review.discovery, name=meta.get("name"), country_code=meta.get("country_code"), region=meta.get("region"), paid_enabled=review.paid_enabled, free_trial_enabled=review.free_trial_enabled, vip_enabled=review.vip_enabled, max_users=review.max_users, traffic_limit_bytes=review.traffic_limit_bytes, priority=review.priority, weight=review.weight, credential_reference=review.credential_reference); state["review"] = review
        callbacks = await _secure_flow_callbacks(update, context, actor, flow_id, ("save_disabled", "save_enable", "test_again", "cancel"))
        await message.reply_text(_review_text(review, language, ssh=state.get("ssh_discovery")), reply_markup=outline_review_keyboard(language, flow_id, callbacks)); return


@permission_required("manage_servers")
async def outline_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.user_data.pop(_STATE, None)
    if state and update.effective_user:
        service = _service(context); ssh_service = _ssh_service(context)
        if ssh_service: ssh_service.cancel(admin_id=update.effective_user.id, flow_id=state.get("flow_id", ""))
        if service: service.cancel_setup(admin_id=update.effective_user.id, flow_id=state.get("flow_id", ""))
    if update.effective_message: await update.effective_message.reply_text(t("admin.outline.cancelled", language=_language(context)))


def register(application: Application) -> None:
    application.add_handler(CommandHandler("cancel", outline_cancel_command), group=5)
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, outline_text), group=5)
    application.add_handler(CallbackQueryHandler(outline_callback, pattern=r"^admin:outline:"), group=5)
