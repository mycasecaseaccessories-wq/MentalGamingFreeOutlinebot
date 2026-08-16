"""Phase 3.1 admin server management handlers."""

from __future__ import annotations

import math
from datetime import datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.handlers.base import admin_required
from app.keyboards.admin_server import server_detail_keyboard, server_list_keyboard, server_menu_keyboard
from app.keyboards.admin_outline_setup import outline_setup_methods_keyboard
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.server_service import ServerService
from locales.translator import t

_STATE = "phase31_server_admin"


def _lang(context) -> str:
    user = context.user_data.get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", None) or getattr(user, "language", None)
    return value if value in {"en", "my"} else "en"


def _actor(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def _service(context) -> ServerService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(ServerService)


def _date(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else "—"


def _server_text(item, language: str) -> str:
    return t("admin.servers.detail", language=language, public_id=item.public_server_id, name=item.name, display_name=item.display_name or "—", host=item.host or "—", provider=item.provider_type, integration=item.integration_type, location=" / ".join(x for x in (item.country_code, item.country_name, item.region) if x) or "—", status=item.status, health=item.health_status, enabled="✅" if item.enabled else "❌", maintenance="✅" if item.maintenance_mode else "❌", priority=item.priority, weight=item.weight, users=f"{item.current_users}/{item.max_users or '∞'}", keys=item.max_keys or "∞", traffic=f"{item.used_traffic_bytes}/{item.traffic_limit_bytes or '∞'}", checked=_date(item.last_health_check_at), synced=_date(item.last_sync_at), notes=item.notes or "—")


async def _menu(update, context):
    if update.effective_message:
        await update.effective_message.reply_text(t("admin.servers.menu", language=_lang(context)), reply_markup=server_menu_keyboard(_lang(context)))


@admin_required
async def server_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; message = update.effective_message; actor = _actor(update); language = _lang(context)
    if query is None or message is None or actor is None: return
    await query.answer()
    parts = (query.data or "").split(":")
    service = _service(context)
    if service is None:
        await message.reply_text(t("common.error", language=language)); return
    try:
        if parts == ["admin", "servers", "menu"]:
            await _menu(update, context); return
        if parts == ["admin", "servers", "add"]:
            await message.reply_text(t("admin.servers.choose_method", language=language), reply_markup=outline_setup_methods_keyboard(language)); return
        if parts == ["admin", "servers", "add", "manual"]:
            context.user_data[_STATE] = {"stage": "name", "actor": actor}
            await message.reply_text(t("admin.servers.manual_name", language=language), reply_markup=ForceReply(selective=True)); return
        if len(parts) == 4 and parts[:3] == ["admin", "servers", "list"]:
            page = max(1, int(parts[3]))
            result = await service.list_servers(page=page)
            if not result.items:
                await message.reply_text(t("admin.servers.empty", language=language), reply_markup=server_menu_keyboard(language)); return
            pages = max(1, math.ceil(result.total / result.page_size))
            text = t("admin.servers.list_title", language=language, page=result.page, pages=pages)
            for item in result.items:
                text += "\n\n" + t("admin.servers.list_item", language=language, public_id=item.public_server_id, name=item.name, status=item.status, health=item.health_status, enabled="✅" if item.enabled else "❌", location=item.country_code or item.region or "—")
            await message.reply_text(text, reply_markup=server_list_keyboard(language, page=result.page, has_previous=result.has_previous, has_next=result.has_next, ids=[item.public_server_id for item in result.items])); return
        if len(parts) == 4 and parts[2] == "view":
            item = await service.get_server(parts[3])
            if item is None: await message.reply_text(t("error.not_found", language=language)); return
            await message.reply_text(_server_text(item, language), reply_markup=server_detail_keyboard(language, public_id=item.public_server_id, enabled=item.enabled, maintenance=item.maintenance_mode, archived=item.archived_at is not None)); return
        if len(parts) == 4 and parts[2] in {"enable", "disable", "archive", "maintenance_on", "maintenance_off"}:
            public_id = parts[3]
            if parts[2] == "enable": result = await service.set_enabled(actor_telegram_id=actor, public_server_id=public_id, enabled=True)
            elif parts[2] == "disable": result = await service.set_enabled(actor_telegram_id=actor, public_server_id=public_id, enabled=False)
            elif parts[2] == "archive": result = await service.archive(actor_telegram_id=actor, public_server_id=public_id)
            else: result = await service.set_maintenance(actor_telegram_id=actor, public_server_id=public_id, maintenance=parts[2] == "maintenance_on")
            if result.is_success:
                item = result.unwrap().server
                await message.reply_text(t("admin.servers.updated", language=language, status=item.status, health=item.health_status, enabled="✅" if item.enabled else "❌"), reply_markup=server_detail_keyboard(language, public_id=item.public_server_id, enabled=item.enabled, maintenance=item.maintenance_mode, archived=item.archived_at is not None))
            else:
                await message.reply_text(t("admin.servers.error", language=language, error=result.error.message if result.error else "Unknown error"))
            return
        if len(parts) == 4 and parts[2] == "edit":
            context.user_data[_STATE] = {"stage": "edit_name", "actor": actor, "public_id": parts[3]}
            await message.reply_text(t("admin.servers.edit_name", language=language), reply_markup=ForceReply(selective=True)); return
        if len(parts) == 4 and parts[2] == "future":
            await message.reply_text(t("admin.servers.coming_soon", language=language, feature=parts[3].replace("_", " ").title()), reply_markup=server_menu_keyboard(language)); return
        if parts == ["admin", "servers", "status"] or parts == ["admin", "servers", "capacity"] or parts == ["admin", "servers", "maintenance"]:
            result = await service.list_servers(page=1)
            if not result.items: await message.reply_text(t("admin.servers.empty", language=language), reply_markup=server_menu_keyboard(language)); return
            await message.reply_text("\n\n".join(_server_text(item, language) for item in result.items), reply_markup=server_menu_keyboard(language)); return
        if parts == ["admin", "servers", "sync"]:
            await message.reply_text(t("admin.servers.coming_soon", language=language, feature="Sync Servers"), reply_markup=server_menu_keyboard(language)); return
    except (TypeError, ValueError):
        await message.reply_text(t("order.invalid_callback", language=language))


@admin_required
async def server_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message; actor = _actor(update); state = context.user_data.get(_STATE) or {}
    if message is None or actor is None or state.get("actor") != actor: return
    language = _lang(context); service = _service(context)
    if service is None: await message.reply_text(t("common.error", language=language)); return
    text = " ".join((message.text or "").split())
    stage = state.get("stage")
    if stage == "name":
        state["name"] = text; state["stage"] = "host"; await message.reply_text(t("admin.servers.manual_host", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "host":
        state["host"] = text; state["stage"] = "country"; await message.reply_text(t("admin.servers.manual_country", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "country":
        state["country_code"] = text; state["stage"] = "region"; await message.reply_text(t("admin.servers.manual_region", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "region":
        state["region"] = text; state["stage"] = "notes"; await message.reply_text(t("admin.servers.manual_notes", language=language), reply_markup=ForceReply(selective=True)); return
    if stage == "notes":
        result = await service.register_manual(actor_telegram_id=actor, name=state.get("name", ""), host=state.get("host"), country_code=state.get("country_code"), region=state.get("region"), notes=text)
        context.user_data.pop(_STATE, None)
        if result.is_success:
            item = result.unwrap().server
            await message.reply_text(t("admin.servers.created", language=language, public_id=item.public_server_id, status=item.status, health=item.health_status), reply_markup=server_detail_keyboard(language, public_id=item.public_server_id, enabled=item.enabled, maintenance=item.maintenance_mode, archived=False))
        else: await message.reply_text(t("admin.servers.error", language=language, error=result.error.message if result.error else "Unknown error"))
        return
    if stage == "edit_name":
        result = await service.update_metadata(actor_telegram_id=actor, public_server_id=state.get("public_id", ""), name=text)
        context.user_data.pop(_STATE, None)
        if result.is_success: await message.reply_text(t("admin.servers.updated", language=language, status=result.unwrap().server.status, health=result.unwrap().server.health_status, enabled="✅" if result.unwrap().server.enabled else "❌"))
        else: await message.reply_text(t("admin.servers.error", language=language, error=result.error.message if result.error else "Unknown error"))


async def cancel_server_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get(_STATE):
        context.user_data.pop(_STATE, None)
        if update.effective_message: await update.effective_message.reply_text(t("admin.servers.cancelled", language=_lang(context)), reply_markup=server_menu_keyboard(_lang(context)))


def register(application: Application) -> None:
    application.add_handler(CommandHandler("cancel", cancel_server_state), group=6)
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, server_text), group=6)
    application.add_handler(CallbackQueryHandler(server_callback, pattern=r"^admin:servers:"), group=6)
