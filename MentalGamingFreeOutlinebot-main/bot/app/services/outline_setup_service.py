"""Unified Outline setup pipeline for API URL, SSH discovery, and Auto-Provision."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.core.result import Failure, Result, Success
from app.events import EventType, bus
from app.integrations.outline_client import OutlineAPIClient, OutlineAPIError
from app.models.outline_setup import OutlineCredentialInput, OutlineDiscoveryResult, OutlineSetupReview, OutlineSetupResult, OutlineSetupSession
from app.security.credential_vault import CredentialVault
from app.security.outline_url_policy import UnsafeOutlineURL, ValidatedOutlineURL, validate_outline_url
from database.models.audit_log import AuditLogORM
from database.models.server import ServerORM
from database.models.user import UserORM
from .base import BaseService


class OutlineSetupService(BaseService):
    """The only service allowed to turn setup credentials into an Outline integration."""

    SESSION_TTL = timedelta(minutes=10)
    _private_states: dict[str, dict] = {}

    def __init__(self, db=None, *, client: OutlineAPIClient | None = None, vault: CredentialVault | None = None) -> None:
        super().__init__(db)
        self.client = client or OutlineAPIClient()
        self.vault = vault or CredentialVault()

    async def start_setup(self, *, admin_id: int, setup_method: str, existing_server_id: str | None = None) -> Result[OutlineSetupSession]:
        if setup_method not in {"api_url", "ssh", "auto_provision"}:
            return Failure("invalid_setup_method", "Unsupported Outline setup method.")
        async with self.db.session() as session:
            actor = await self._admin(session, admin_id)
            if actor is None: return Failure("unauthorized", "Server management permission required.")
            if existing_server_id:
                row = (await session.execute(select(ServerORM).where(ServerORM.public_server_id == existing_server_id))).scalar_one_or_none()
                if row is None or row.archived_at is not None: return Failure("not_found", "Target server not found.")
        now = datetime.now(timezone.utc)
        flow = OutlineSetupSession(flow_id=uuid4().hex, admin_id=admin_id, setup_method=setup_method, existing_server_id=existing_server_id, created_at=now, expires_at=now + self.SESSION_TTL)
        self._private_states[flow.flow_id] = {"session": flow}
        return Success(flow)

    async def validate_and_verify(self, *, admin_id: int, flow_id: str, credential: OutlineCredentialInput, allow_private: bool = False) -> Result[OutlineSetupReview]:
        state = self._active_state(admin_id, flow_id)
        if state is None: return Failure("setup_expired", "Setup session expired or is not owned by this admin.")
        if state["session"].setup_method != credential.source and not (credential.source == "api_url" and state["session"].setup_method == "api_url"):
            return Failure("invalid_setup_method", "Credential source does not match setup method.")
        try:
            validated = await validate_outline_url(credential.management_url, allow_private=allow_private)
            discovery = await self.client.verify_management_api(validated, credential)
        except (UnsafeOutlineURL, OutlineAPIError) as exc:
            return Failure("outline_verification_failed", str(exc))
        except Exception:
            self._private_states.pop(flow_id, None)
            return Failure("outline_verification_failed", "Outline API verification failed.")
        reference = CredentialVault.reference(credential.management_url)
        state["credential"] = credential
        state["validated_url"] = validated
        state["discovery"] = discovery
        state["credential_reference"] = reference
        async with self.db.session() as session:
            existing = None
            if state["session"].existing_server_id:
                existing = (await session.execute(select(ServerORM).where(ServerORM.public_server_id == state["session"].existing_server_id))).scalar_one_or_none()
            name = existing.name if existing else discovery.safe_metadata.get("server_name")
            country = existing.country_code if existing else None
            region = existing.region if existing else None
            caps = existing or None
            return Success(OutlineSetupReview(flow_id=flow_id, server_public_id=existing.public_server_id if existing else None, source=credential.source, discovery=discovery, name=name, country_code=country, region=region, paid_enabled=bool(getattr(caps, "paid_enabled", False)), free_trial_enabled=bool(getattr(caps, "free_trial_enabled", False)), vip_enabled=bool(getattr(caps, "vip_enabled", False)), max_users=getattr(caps, "max_users", None), traffic_limit_bytes=getattr(caps, "traffic_limit_bytes", None), priority=getattr(caps, "priority", 100), weight=getattr(caps, "weight", 1), credential_reference=reference))

    async def reverify(self, *, admin_id: int, flow_id: str, allow_private: bool = False) -> Result[OutlineSetupReview]:
        state = self._active_state(admin_id, flow_id)
        if state is None or "credential" not in state:
            return Failure("setup_expired", "Setup session expired or is not owned by this admin.")
        credential: OutlineCredentialInput = state["credential"]
        return await self.validate_and_verify(admin_id=admin_id, flow_id=flow_id, credential=credential, allow_private=allow_private)

    async def save_verified(self, *, admin_id: int, flow_id: str, name: str, country_code: str | None, region: str | None, paid_enabled: bool = False, free_trial_enabled: bool = False, vip_enabled: bool = False, max_users: int | None = None, traffic_limit_bytes: int | None = None, priority: int = 100, weight: int = 1, enable: bool = False) -> Result[OutlineSetupResult]:
        state = self._active_state(admin_id, flow_id)
        if state is None or "discovery" not in state or "credential" not in state: return Failure("verification_required", "A successful Outline verification is required before saving.")
        session_info: OutlineSetupSession = state["session"]; discovery: OutlineDiscoveryResult = state["discovery"]; credential: OutlineCredentialInput = state["credential"]; secret_reference = state["credential_reference"]
        async with self.db.session() as session:
            actor = await self._admin(session, admin_id)
            if actor is None: return Failure("unauthorized", "Server management permission required.")
            row = None
            if session_info.existing_server_id:
                row = (await session.execute(select(ServerORM).where(ServerORM.public_server_id == session_info.existing_server_id))).scalar_one_or_none()
                if row is None or row.archived_at is not None: return Failure("not_found", "Target server not found.")
            else:
                row = (await session.execute(select(ServerORM).where(ServerORM.secret_reference == secret_reference, ServerORM.archived_at.is_(None)))).scalar_one_or_none()
            if row is not None and row.secret_reference == secret_reference and row.api_compatible:
                result = OutlineSetupResult(row.public_server_id, secret_reference, row.status, row.enabled, discovery)
                self._private_states.pop(flow_id, None)
                return Success(result)
            if enable and not discovery.api_compatible: return Failure("verification_required", "Only a verified compatible Outline API may be enabled.")
            if row is None:
                row = ServerORM(public_server_id=await self._new_public_id(session), name=self._safe_name(name), display_name=self._safe_name(name), host=discovery.host, provider_type="outline", integration_type="outline_api", country_code=self._safe_country(country_code), region=(region or None), status=ServerORM.STATUS_ONLINE if enable else ServerORM.STATUS_DISABLED, health_status=ServerORM.HEALTH_OK, enabled=bool(enable), is_active=bool(enable), paid_enabled=paid_enabled, free_trial_enabled=free_trial_enabled, vip_enabled=vip_enabled, max_users=max_users, traffic_limit_bytes=traffic_limit_bytes, priority=max(0, priority), weight=max(1, weight), provider_server_id=discovery.provider_server_id, cert_sha256=credential.cert_sha256, secret_reference=secret_reference, credential_ciphertext=self.vault.encrypt(credential.management_url), verified_at=discovery.verified_at, outline_version=discovery.outline_version, api_compatible=True, metrics_available=discovery.metrics_available, existing_key_count=discovery.existing_key_count, metadata_json=discovery.safe_metadata)
                session.add(row); await session.flush(); action = "server.outline_connected"
            else:
                row.name=self._safe_name(name); row.display_name=row.name; row.host=discovery.host; row.provider_type="outline"; row.integration_type="outline_api"; row.country_code=self._safe_country(country_code); row.region=(region or None); row.status=ServerORM.STATUS_ONLINE if enable else ServerORM.STATUS_DISABLED; row.health_status=ServerORM.HEALTH_OK; row.enabled=bool(enable); row.is_active=bool(enable); row.paid_enabled=paid_enabled; row.free_trial_enabled=free_trial_enabled; row.vip_enabled=vip_enabled; row.max_users=max_users; row.traffic_limit_bytes=traffic_limit_bytes; row.priority=max(0, priority); row.weight=max(1, weight); row.provider_server_id=discovery.provider_server_id; row.cert_sha256=credential.cert_sha256; row.secret_reference=secret_reference; row.credential_ciphertext=self.vault.encrypt(credential.management_url); row.verified_at=discovery.verified_at; row.outline_version=discovery.outline_version; row.api_compatible=True; row.metrics_available=discovery.metrics_available; row.existing_key_count=discovery.existing_key_count; row.metadata_json=discovery.safe_metadata; action = "server.outline_reconnected"
            session.add(AuditLogORM(actor_id=actor.id, action=action, entity_type="Server", entity_id=row.id, old_value=None, new_value=json.dumps({"public_server_id": row.public_server_id, "provider_type": row.provider_type, "integration_type": row.integration_type, "status": row.status, "health_status": row.health_status, "enabled": row.enabled, "secret_reference": secret_reference, "verified_at": discovery.verified_at.isoformat()}), note="Outline API verified and credential stored securely; raw URL omitted."))
            result = OutlineSetupResult(row.public_server_id, secret_reference, row.status, row.enabled, discovery)
        self._private_states.pop(flow_id, None)
        await bus.emit(EventType.SERVER_UPDATED, public_server_id=result.server_public_id, actor_telegram_id=admin_id, source=credential.source, verified=True, enabled=result.enabled)
        return Success(result)

    def cancel_setup(self, *, admin_id: int, flow_id: str) -> bool:
        state = self._private_states.get(flow_id)
        if state is None or state["session"].admin_id != admin_id: return False
        self._private_states.pop(flow_id, None); return True

    def _active_state(self, admin_id: int, flow_id: str) -> dict | None:
        state = self._private_states.get(flow_id)
        if state is None: return None
        if state["session"].admin_id != admin_id:
            return None
        if state["session"].expires_at <= datetime.now(timezone.utc):
            self._private_states.pop(flow_id, None)
            return None
        return state

    async def _admin(self, session, telegram_id: int):
        actor = (await session.execute(select(UserORM).where(UserORM.telegram_id == telegram_id).limit(1))).scalar_one_or_none()
        if actor is None or actor.role != "admin" or not actor.is_active or actor.status in {"banned", "suspended", "inactive"}: return None
        return actor

    async def _new_public_id(self, session) -> str:
        for _ in range(10):
            candidate = f"SRV-{secrets.token_hex(4).upper()}"
            if (await session.execute(select(ServerORM.id).where(ServerORM.public_server_id == candidate))).scalar_one_or_none() is None: return candidate
        raise RuntimeError("Could not allocate a server public identifier")

    @staticmethod
    def _safe_name(value: str) -> str:
        clean = " ".join((value or "").split())
        if not 2 <= len(clean) <= 128 or any(ord(ch) < 32 for ch in clean): raise ValueError("Server name must be 2–128 printable characters.")
        return clean

    @staticmethod
    def _safe_country(value: str | None) -> str | None:
        if not value: return None
        clean = value.strip().upper()
        if len(clean) != 2 or not clean.isalpha(): raise ValueError("Country code must use two letters.")
        return clean
