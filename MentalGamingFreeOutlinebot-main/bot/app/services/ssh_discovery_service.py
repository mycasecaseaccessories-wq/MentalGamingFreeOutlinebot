"""Phase 3.3 VPS discovery service; all Outline verification is delegated to 3.2."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

from app.core.result import Failure, Result, Success
from app.integrations.ssh_provider import OutlineNotFound, SSHDiscoveryError, SSHDiscoveryProvider
from app.models.outline_setup import OutlineCredentialInput, OutlineSetupReview
from app.models.ssh_discovery import OutlineSSHDiscoveryResult, SSHCredentialInput, SSHDiscoveryHandoff
from app.security.ssh_policy import UnsafeSSHTarget, validate_ssh_input
from .base import BaseService
from .outline_setup_service import OutlineSetupService


class SSHDiscoveryService(BaseService):
    SESSION_TTL = timedelta(minutes=10)
    _states: dict[str, dict] = {}

    def __init__(self, db=None, *, provider: SSHDiscoveryProvider | None = None, outline_setup: OutlineSetupService | None = None) -> None:
        super().__init__(db)
        self.provider = provider or SSHDiscoveryProvider()
        self.outline_setup = outline_setup or OutlineSetupService(db)

    async def start_setup(self, *, admin_id: int, existing_server_id: str | None = None) -> Result[str]:
        flow = await self.outline_setup.start_setup(admin_id=admin_id, setup_method="ssh", existing_server_id=existing_server_id)
        if not flow.is_success: return Failure(flow.error.code, flow.error.message)
        self._states[flow.unwrap().flow_id] = {"admin_id": admin_id, "created_at": datetime.now(timezone.utc), "expires_at": datetime.now(timezone.utc) + self.SESSION_TTL}
        return Success(flow.unwrap().flow_id)

    def set_connection_details(self, *, admin_id: int, flow_id: str, host: str, port: int, username: str) -> Result[bool]:
        state = self._states.get(flow_id)
        if not self._active(admin_id, flow_id) or state is None:
            return Failure("setup_expired", "SSH setup session expired or is not owned by this admin.")
        state["connection"] = {"host": host, "port": port, "username": username}
        return Success(True)

    def set_auth_secret(self, *, admin_id: int, flow_id: str, auth_method: str, secret: str) -> Result[bool]:
        state = self._states.get(flow_id)
        if not self._active(admin_id, flow_id) or state is None:
            return Failure("setup_expired", "SSH setup session expired or is not owned by this admin.")
        state["auth_method"] = auth_method
        state["secret"] = secret
        return Success(True)

    def set_host_key_fingerprint(self, *, admin_id: int, flow_id: str, fingerprint: str) -> Result[bool]:
        state = self._states.get(flow_id)
        if not self._active(admin_id, flow_id) or state is None:
            return Failure("setup_expired", "SSH setup session expired or is not owned by this admin.")
        value = fingerprint.strip()
        if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]+={0,2}", value):
            return Failure("invalid_host_key", "SSH host-key fingerprint must use SHA256:<base64> format.")
        state["fingerprint"] = value
        return Success(True)

    def build_credential(self, *, admin_id: int, flow_id: str) -> Result[SSHCredentialInput]:
        state = self._states.get(flow_id)
        if not self._active(admin_id, flow_id) or state is None:
            return Failure("setup_expired", "SSH setup session expired or is not owned by this admin.")
        connection = state.get("connection") or {}; method = state.get("auth_method"); secret = state.get("secret")
        if not connection or method not in {"password", "private_key"} or not secret:
            return Failure("invalid_ssh_input", "SSH connection details are incomplete.")
        return Success(SSHCredentialInput(host=connection["host"], port=connection["port"], username=connection["username"], auth_method=method, password=secret if method == "password" else None, private_key=secret if method == "private_key" else None, expected_host_key_fingerprint=state.get("fingerprint")))

    def prepare_credentials(self, *, admin_id: int, flow_id: str, credential: SSHCredentialInput) -> Result[bool]:
        if not self._active(admin_id, flow_id): return Failure("setup_expired", "SSH setup session expired or is not owned by this admin.")
        try:
            normalized = validate_ssh_input(credential)
        except UnsafeSSHTarget as exc:
            return Failure("invalid_ssh_input", str(exc))
        self._states[flow_id]["credential"] = normalized
        self._states[flow_id].pop("secret", None)
        return Success(True)

    async def discover_stored(self, *, admin_id: int, flow_id: str, allow_private: bool = False) -> Result[SSHDiscoveryHandoff | OutlineSSHDiscoveryResult]:
        state = self._states.get(flow_id)
        if not self._active(admin_id, flow_id) or not state or "credential" not in state:
            return Failure("setup_expired", "SSH setup session expired or is not owned by this admin.")
        return await self.discover(admin_id=admin_id, flow_id=flow_id, credential=state["credential"], allow_private=allow_private)

    async def discover(self, *, admin_id: int, flow_id: str, credential: SSHCredentialInput, allow_private: bool = False) -> Result[SSHDiscoveryHandoff | OutlineSSHDiscoveryResult]:
        if not self._active(admin_id, flow_id): return Failure("setup_expired", "SSH setup session expired or is not owned by this admin.")
        try:
            normalized = validate_ssh_input(credential, allow_private=allow_private)
            discovery = await self.provider.discover(normalized)
        except (UnsafeSSHTarget, SSHDiscoveryError) as exc:
            self._states.pop(flow_id, None)
            self.outline_setup.cancel_setup(admin_id=admin_id, flow_id=flow_id)
            return Failure("ssh_discovery_failed", str(exc))
        if not discovery.outline_found or not discovery.management_url:
            self._states.pop(flow_id, None)
            self.outline_setup.cancel_setup(admin_id=admin_id, flow_id=flow_id)
            return Success(discovery)
        # Mandatory handoff: SSH never verifies or persists Outline credentials itself.
        review = await self.outline_setup.validate_and_verify(admin_id=admin_id, flow_id=flow_id, credential=OutlineCredentialInput(management_url=discovery.management_url, cert_sha256=discovery.cert_sha256, source="ssh"), allow_private=allow_private)
        self._states.pop(flow_id, None)
        if not review.is_success:
            self.outline_setup.cancel_setup(admin_id=admin_id, flow_id=flow_id)
            return Failure(review.error.code, review.error.message)
        return Success(SSHDiscoveryHandoff(discovery=discovery, outline_review=review.unwrap()))

    def cancel(self, *, admin_id: int, flow_id: str) -> bool:
        state = self._states.get(flow_id)
        if state is None or state["admin_id"] != admin_id: return False
        self._states.pop(flow_id, None)
        return self.outline_setup.cancel_setup(admin_id=admin_id, flow_id=flow_id)

    def _active(self, admin_id: int, flow_id: str) -> bool:
        state = self._states.get(flow_id)
        if state is None or state["admin_id"] != admin_id: return False
        if state["expires_at"] <= datetime.now(timezone.utc):
            self._states.pop(flow_id, None)
            self.outline_setup.cancel_setup(admin_id=admin_id, flow_id=flow_id)
            return False
        return True
