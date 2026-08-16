"""Authoritative Phase 3.1 server registry and admin management service."""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.result import Failure, Result, Success
from app.events import EventType, bus
from app.models.server_management import ServerItem, ServerMutation, ServerPage
from database.models.audit_log import AuditLogORM
from database.models.server import ServerORM
from database.models.user import UserORM
from database.repositories.server_repository import ServerRepository
from .base import BaseService

_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}[A-Za-z0-9]$")
_NAME_RE = re.compile(r"^[^\x00-\x1f\x7f]{2,128}$")


class ServerService(BaseService):
    """Manage metadata and administrative state; never performs connectivity."""

    PAGE_SIZE = 8

    async def list_servers(self, *, page: int = 1, page_size: int = PAGE_SIZE, include_archived: bool = False) -> ServerPage:
        page = max(1, int(page)); page_size = min(50, max(1, int(page_size)))
        async with self.db.session() as session:
            repo = ServerRepository(session)
            total = await repo.count_management(include_archived=include_archived)
            rows = await repo.list_management(offset=(page - 1) * page_size, limit=page_size, include_archived=include_archived)
        return ServerPage(tuple(self._item(row) for row in rows), page, page_size, total, page > 1, page * page_size < total)

    async def get_server(self, public_server_id: str) -> ServerItem | None:
        async with self.db.session() as session:
            row = await ServerRepository(session).get_by_public_id(public_server_id)
            return None if row is None else self._item(row)

    async def register_manual(self, *, actor_telegram_id: int, name: str, host: str | None = None, country_code: str | None = None, country_name: str | None = None, region: str | None = None, notes: str | None = None) -> Result[ServerMutation]:
        try:
            clean_name = self._name(name)
            clean_host = self._host(host) if host else None
            clean_country = self._country(country_code) if country_code else None
        except ValueError as exc:
            return Failure("validation_error", str(exc))
        async with self.db.session() as session:
            actor = await self._authorized_actor(session, actor_telegram_id)
            if actor is None:
                return Failure("unauthorized", "Server management permission required.")
            public_id = await self._new_public_id(session)
            row = ServerORM(
                public_server_id=public_id, name=clean_name, display_name=clean_name,
                host=clean_host, provider_type="outline", integration_type="manual",
                country_code=clean_country, country_name=(country_name or None), region=(region or None),
                status=ServerORM.STATUS_UNKNOWN, health_status=ServerORM.HEALTH_UNKNOWN,
                enabled=False, is_active=False, maintenance_mode=False,
                notes=(notes or None), api_url=None, cert_sha256=None,
            )
            session.add(row); await session.flush()
            session.add(AuditLogORM(actor_id=actor.id, action="server.added", entity_type="Server", entity_id=row.id, old_value=None, new_value=json.dumps({"public_server_id": public_id, "status": row.status, "health_status": row.health_status, "enabled": row.enabled}), note="Manual server metadata registered; verification not performed."))
            item = self._item(row)
        await bus.emit(EventType.SERVER_ADDED, public_server_id=item.public_server_id, actor_telegram_id=actor_telegram_id)
        return Success(ServerMutation(item))

    async def update_metadata(self, *, actor_telegram_id: int, public_server_id: str, **changes) -> Result[ServerMutation]:
        allowed = {"name", "display_name", "host", "country_code", "country_name", "region", "notes", "priority", "weight", "max_users", "max_keys", "traffic_limit_bytes"}
        unknown = set(changes) - allowed
        if unknown:
            return Failure("validation_error", f"Unsupported server fields: {', '.join(sorted(unknown))}")
        try:
            if "name" in changes: changes["name"] = self._name(changes["name"])
            if "host" in changes and changes["host"]: changes["host"] = self._host(changes["host"])
            if "country_code" in changes and changes["country_code"]: changes["country_code"] = self._country(changes["country_code"])
        except ValueError as exc:
            return Failure("validation_error", str(exc))
        async with self.db.session() as session:
            actor = await self._authorized_actor(session, actor_telegram_id)
            row = await ServerRepository(session).get_by_public_id(public_server_id)
            if actor is None: return Failure("unauthorized", "Server management permission required.")
            if row is None: return Failure("not_found", "Server not found.")
            if row.archived_at is not None: return Failure("archived", "Archived servers cannot be edited.")
            old = {key: getattr(row, key) for key in changes}
            for key, value in changes.items(): setattr(row, key, value)
            await session.flush()
            session.add(AuditLogORM(actor_id=actor.id, action="server.updated", entity_type="Server", entity_id=row.id, old_value=json.dumps(old, default=str), new_value=json.dumps(changes, default=str), note="Server metadata updated."))
            item = self._item(row)
        await bus.emit(EventType.SERVER_UPDATED, public_server_id=item.public_server_id, actor_telegram_id=actor_telegram_id)
        return Success(ServerMutation(item))

    async def set_enabled(self, *, actor_telegram_id: int, public_server_id: str, enabled: bool) -> Result[ServerMutation]:
        async with self.db.session() as session:
            actor = await self._authorized_actor(session, actor_telegram_id)
            row = await ServerRepository(session).get_by_public_id(public_server_id)
            if actor is None: return Failure("unauthorized", "Server management permission required.")
            if row is None: return Failure("not_found", "Server not found.")
            if row.archived_at is not None: return Failure("archived", "Archived servers cannot be enabled.")
            if enabled and (row.status != ServerORM.STATUS_ONLINE or row.health_status != ServerORM.HEALTH_OK):
                return Failure("server_not_verified", "Only a verified online server can be enabled.")
            row.enabled = bool(enabled); row.is_active = bool(enabled)
            if not enabled and row.status != ServerORM.STATUS_MAINTENANCE: row.status = ServerORM.STATUS_DISABLED
            await session.flush()
            session.add(AuditLogORM(actor_id=actor.id, action="server.enabled" if enabled else "server.disabled", entity_type="Server", entity_id=row.id, new_value=json.dumps({"enabled": row.enabled, "status": row.status}), note="Administrative enable state changed."))
            item = self._item(row)
        await bus.emit(EventType.SERVER_UPDATED, public_server_id=item.public_server_id, actor_telegram_id=actor_telegram_id, enabled=enabled)
        return Success(ServerMutation(item))

    async def set_maintenance(self, *, actor_telegram_id: int, public_server_id: str, maintenance: bool) -> Result[ServerMutation]:
        async with self.db.session() as session:
            actor = await self._authorized_actor(session, actor_telegram_id); row = await ServerRepository(session).get_by_public_id(public_server_id)
            if actor is None: return Failure("unauthorized", "Server management permission required.")
            if row is None: return Failure("not_found", "Server not found.")
            if row.archived_at is not None: return Failure("archived", "Archived servers cannot change maintenance state.")
            row.maintenance_mode = bool(maintenance)
            if maintenance: row.status = ServerORM.STATUS_MAINTENANCE; row.enabled = False; row.is_active = False
            elif row.status == ServerORM.STATUS_MAINTENANCE: row.status = ServerORM.STATUS_DISABLED if not row.enabled else ServerORM.STATUS_UNKNOWN
            await session.flush()
            session.add(AuditLogORM(actor_id=actor.id, action="server.maintenance_enabled" if maintenance else "server.maintenance_disabled", entity_type="Server", entity_id=row.id, new_value=json.dumps({"maintenance_mode": row.maintenance_mode, "status": row.status}), note="Maintenance state changed."))
            item = self._item(row)
        await bus.emit(EventType.SERVER_UPDATED, public_server_id=item.public_server_id, actor_telegram_id=actor_telegram_id, maintenance=maintenance)
        return Success(ServerMutation(item))

    async def archive(self, *, actor_telegram_id: int, public_server_id: str) -> Result[ServerMutation]:
        async with self.db.session() as session:
            actor = await self._authorized_actor(session, actor_telegram_id); row = await ServerRepository(session).get_by_public_id(public_server_id)
            if actor is None: return Failure("unauthorized", "Server management permission required.")
            if row is None: return Failure("not_found", "Server not found.")
            if row.archived_at is not None: return Success(ServerMutation(self._item(row), changed=False, idempotent=True))
            row.archived_at = datetime.now(timezone.utc); row.enabled = False; row.is_active = False; row.maintenance_mode = False; row.status = ServerORM.STATUS_ARCHIVED
            await session.flush()
            session.add(AuditLogORM(actor_id=actor.id, action="server.archived", entity_type="Server", entity_id=row.id, new_value=json.dumps({"status": row.status, "enabled": row.enabled}), note="Server archived; retained for history."))
            item = self._item(row)
        await bus.emit(EventType.SERVER_REMOVED, public_server_id=item.public_server_id, actor_telegram_id=actor_telegram_id)
        return Success(ServerMutation(item))

    async def _authorized_actor(self, session, telegram_id: int):
        actor = (await session.execute(select(UserORM).where(UserORM.telegram_id == telegram_id).limit(1))).scalar_one_or_none()
        if actor is None or actor.role != "admin" or not actor.is_active or actor.status in {"banned", "suspended", "inactive"}: return None
        return actor

    async def _new_public_id(self, session) -> str:
        for _ in range(10):
            candidate = f"SRV-{secrets.token_hex(4).upper()}"
            exists = (await session.execute(select(ServerORM.id).where(ServerORM.public_server_id == candidate))).scalar_one_or_none()
            if exists is None: return candidate
        raise RuntimeError("Could not allocate a unique public server ID")

    @staticmethod
    def _name(value: str) -> str:
        value = " ".join((value or "").split())
        if not _NAME_RE.fullmatch(value): raise ValueError("Server name must be 2–128 printable characters.")
        return value

    @staticmethod
    def _host(value: str) -> str:
        value = (value or "").strip()
        if not _HOST_RE.fullmatch(value): raise ValueError("Host must be a valid hostname or IP address.")
        return value

    @staticmethod
    def _country(value: str) -> str:
        value = (value or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", value): raise ValueError("Country code must be ISO-style two letters.")
        return value

    @staticmethod
    def _item(row: ServerORM) -> ServerItem:
        return ServerItem(public_server_id=row.public_server_id, name=row.name, display_name=row.display_name, host=row.host, provider_type=row.provider_type, integration_type=row.integration_type, region=row.region, country_code=row.country_code, country_name=row.country_name, status=row.status, health_status=row.health_status, enabled=row.enabled, maintenance_mode=row.maintenance_mode, priority=row.priority, weight=row.weight, max_users=row.max_users, current_users=row.current_users, max_keys=row.max_keys, traffic_limit_bytes=row.traffic_limit_bytes, used_traffic_bytes=row.used_traffic_bytes, free_trial_enabled=row.free_trial_enabled, paid_enabled=row.paid_enabled, vip_enabled=row.vip_enabled, last_health_check_at=row.last_health_check_at, last_sync_at=row.last_sync_at, archived_at=row.archived_at, notes=row.notes)
