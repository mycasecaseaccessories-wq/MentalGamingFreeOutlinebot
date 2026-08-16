"""Admin-only Outline Auto-Provisioning orchestration.

This service owns the provisioning boundary but delegates Outline verification and
persistence to OutlineSetupService.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from app.core.result import Failure, Result, Success
from app.events import EventType, bus
from app.integrations.outline_installer import OutlineInstaller
from app.integrations.ssh_provider import SSHDiscoveryError, SSHDiscoveryProvider
from app.models.outline_setup import OutlineCredentialInput
from app.models.provisioning import PreflightResult, ProvisioningPlan, ProvisioningPolicy, ProvisioningSession, ProvisioningStatus
from app.models.ssh_discovery import SSHCredentialInput
from .outline_setup_service import OutlineSetupService


class OutlineProvisioningService:
    SESSION_TTL = timedelta(minutes=15)

    def __init__(self, *, outline_setup: OutlineSetupService, ssh: SSHDiscoveryProvider, installer: OutlineInstaller | None = None, policy: ProvisioningPolicy | None = None) -> None:
        self.outline_setup = outline_setup
        self.ssh = ssh
        self.installer = installer or OutlineInstaller()
        self.policy = policy or ProvisioningPolicy()
        self._sessions: dict[str, dict[str, object]] = {}

    async def start(self, *, admin_id: int, credential: SSHCredentialInput) -> Result[ProvisioningSession]:
        setup = await self.outline_setup.start_setup(admin_id=admin_id, setup_method="auto_provision")
        if setup.is_failure:
            return setup
        now = datetime.now(timezone.utc)
        session = ProvisioningSession(flow_id=setup.value.flow_id, admin_id=admin_id, credential=credential, created_at=now, expires_at=now + self.SESSION_TTL)
        self._sessions[session.flow_id] = {"session": session, "confirmed": False, "install_started": False, "status": ProvisioningStatus.STARTED}
        await bus.emit(EventType.PROVISION_STARTED, flow_id=session.flow_id, admin_id=admin_id, host=credential.host, source="auto_provision")
        return Success(session)

    async def preflight(self, *, admin_id: int, flow_id: str) -> Result[ProvisioningPlan | object]:
        state = self._active(admin_id, flow_id)
        if state is None:
            return Failure("provisioning_expired", "Provisioning session expired or is not owned by this admin.")
        session: ProvisioningSession = state["session"]  # type: ignore[assignment]
        try:
            discovered = await self.ssh.discover(session.credential)
            if discovered.outline_found and discovered.management_url:
                credential = OutlineCredentialInput(management_url=discovered.management_url, cert_sha256=discovered.cert_sha256, source="auto_provision")
                verified = await self.outline_setup.validate_and_verify(admin_id=admin_id, flow_id=flow_id, credential=credential)
                if verified.is_failure:
                    return verified
                state["status"] = ProvisioningStatus.EXISTING_OUTLINE_FOUND
                state["review"] = verified.value
                return Success(verified.value)
            raw = await self.ssh.run_preflight(session.credential, self.policy)
            result = self._parse_preflight(session.credential.host, raw)
        except (SSHDiscoveryError, ValueError) as exc:
            state["status"] = ProvisioningStatus.FAILED
            return Failure("preflight_failed", str(exc))
        if not result.passed:
            state["status"] = ProvisioningStatus.FAILED
            return Failure("preflight_rejected", "The VPS did not meet the provisioning policy.")
        plan = ProvisioningPlan(flow_id=flow_id, host=session.credential.host, preflight=result, installer_strategy=self.policy.installer_strategy, installer_version="v1", expected_changes=("Install the approved Outline Server package", "Install or reuse Docker only as required by the official installer", "Start the Outline management service"), warnings=result.warnings, requires_confirmation=True)
        state["status"] = ProvisioningStatus.AWAITING_CONFIRMATION
        state["plan"] = plan
        await bus.emit(EventType.PROVISION_PREFLIGHT_COMPLETED, flow_id=flow_id, admin_id=admin_id, host=session.credential.host, passed=True, warnings=list(result.warnings))
        state["confirmation_nonce"] = secrets.token_urlsafe(24)
        return Success(plan)

    def confirmation_token(self, *, admin_id: int, flow_id: str) -> str | None:
        state = self._active(admin_id, flow_id)
        return str(state.get("confirmation_nonce")) if state else None

    def confirm(self, *, admin_id: int, flow_id: str, token: str) -> Result[ProvisioningPlan]:
        state = self._active(admin_id, flow_id)
        if state is None:
            return Failure("provisioning_expired", "Provisioning session expired or is not owned by this admin.")
        if state.get("status") != ProvisioningStatus.AWAITING_CONFIRMATION or not secrets.compare_digest(str(state.get("confirmation_nonce", "")), token):
            return Failure("confirmation_required", "A valid one-time confirmation is required before installation.")
        state["confirmed"] = True
        state["status"] = ProvisioningStatus.INSTALLING
        return Success(state["plan"])  # type: ignore[arg-type]

    async def install(self, *, admin_id: int, flow_id: str) -> Result[object]:
        state = self._active(admin_id, flow_id)
        if state is None:
            return Failure("provisioning_expired", "Provisioning session expired or is not owned by this admin.")
        if state.get("status") != ProvisioningStatus.INSTALLING or not state.get("confirmed"):
            return Failure("confirmation_required", "Installation is blocked until the admin confirmation gate is completed.")
        if state.get("install_started"):
            return Failure("already_installing", "This provisioning flow has already started installation.")
        state["install_started"] = True
        await bus.emit(EventType.PROVISION_INSTALLATION_STARTED, flow_id=flow_id, admin_id=admin_id)
        session: ProvisioningSession = state["session"]  # type: ignore[assignment]
        plan: ProvisioningPlan = state["plan"]  # type: ignore[assignment]
        try:
            command = self.installer.build_command(self.policy, use_sudo=plan.preflight.privilege_mode != "root")
            exit_code, stdout, stderr = await self.ssh.run_installer(session.credential, command, timeout_seconds=self.policy.install_timeout_seconds)
            parsed = self.installer.parse_result(stdout, host=session.credential.host, strategy=self.policy.installer_strategy)
            if exit_code != 0 or not parsed.success:
                state["status"] = ProvisioningStatus.FAILED
                await bus.emit(EventType.PROVISION_FAILED, flow_id=flow_id, admin_id=admin_id, stage="installation")
                return Failure("installation_failed", parsed.diagnostics or "Outline installer failed.")
            state["status"] = ProvisioningStatus.INSTALLED_PENDING_VERIFICATION
            setup_credential = OutlineCredentialInput(management_url=parsed.management_url or "", cert_sha256=parsed.cert_sha256, source="auto_provision")
            verified = await self.outline_setup.validate_and_verify(admin_id=admin_id, flow_id=flow_id, credential=setup_credential)
            if verified.is_failure:
                state["status"] = ProvisioningStatus.VERIFICATION_FAILED
                await bus.emit(EventType.PROVISION_VERIFICATION_FAILED, flow_id=flow_id, admin_id=admin_id)
                return verified
            state["status"] = ProvisioningStatus.COMPLETED
            await bus.emit(EventType.PROVISION_INSTALLATION_COMPLETED, flow_id=flow_id, admin_id=admin_id)
            await bus.emit(EventType.PROVISION_COMPLETED, flow_id=flow_id, admin_id=admin_id)
            state["review"] = verified.value
            return Success(verified.value)
        except (SSHDiscoveryError, ValueError) as exc:
            state["status"] = ProvisioningStatus.FAILED
            await bus.emit(EventType.PROVISION_FAILED, flow_id=flow_id, admin_id=admin_id, stage="installation")
            return Failure("installation_failed", str(exc))

    def cancel(self, *, admin_id: int, flow_id: str) -> Result[bool]:
        state = self._active(admin_id, flow_id)
        if state is None:
            return Failure("provisioning_expired", "Provisioning session expired or is not owned by this admin.")
        if state.get("install_started"):
            return Failure("installation_started", "Installation already started; remote changes are not rolled back.")
        self._sessions.pop(flow_id, None)
        self.outline_setup.cancel_setup(admin_id=admin_id, flow_id=flow_id)
        return Success(True)

    def _active(self, admin_id: int, flow_id: str) -> dict[str, object] | None:
        state = self._sessions.get(flow_id)
        if not state:
            return None
        session: ProvisioningSession = state["session"]  # type: ignore[assignment]
        if session.admin_id != admin_id or session.expires_at <= datetime.now(timezone.utc):
            self._sessions.pop(flow_id, None)
            return None
        return state

    def _parse_preflight(self, host: str, raw: dict[str, str]) -> PreflightResult:
        os_name = self._value(raw.get("os_release", ""), r'^PRETTY_NAME=["\']?([^"\'\n]+)')
        arch = raw.get("uname", "").strip().splitlines()[0] if raw.get("uname", "").strip() else None
        identity = raw.get("identity", "").splitlines()
        uid = identity[0].strip() if identity else ""
        groups = identity[1] if len(identity) > 1 else ""
        privilege = "root" if uid == "0" else ("sudo" if "sudo" in groups.split() else "unprivileged")
        disk = self._int_from(raw.get("disk", ""), r"^\S+\s+\d+\s+\d+\s+(\d+)\s+\d+%\s+/\s*$")
        memory = self._int_from(raw.get("memory", ""), r"(\d+)")
        commands = tuple(x.strip() for x in raw.get("commands", "").splitlines() if x.strip())
        ports = tuple(sorted({int(x) for x in re.findall(r":(\d+)\b", raw.get("ports", "")) if x.isdigit()}))
        failures: list[str] = []
        warnings: list[str] = []
        lowered_os = (os_name or "").lower()
        if not any(token in lowered_os for token in self.policy.supported_os_tokens): failures.append("unsupported_os")
        if arch not in self.policy.supported_architectures: failures.append("unsupported_architecture")
        if privilege == "unprivileged": failures.append("insufficient_privilege")
        if disk is None or disk < self.policy.min_disk_mb: failures.append("insufficient_disk")
        if memory is None or memory < self.policy.min_memory_mb: failures.append("insufficient_memory")
        if "curl" not in commands: failures.append("curl_missing")
        if not raw.get("dns", "").strip(): failures.append("dns_unavailable")
        if not raw.get("https", "").startswith("HTTP/"): failures.append("https_unavailable")
        if 443 in ports: warnings.append("https_port_in_use")
        if raw.get("docker", "").strip(): warnings.append("docker_already_present")
        return PreflightResult(host=host, os_name=os_name, architecture=arch, privilege_mode=privilege, docker_available=bool(raw.get("docker", "").strip()), disk_free_mb=disk, memory_available_mb=memory, dns_ok=bool(raw.get("dns", "").strip()), https_ok=raw.get("https", "").startswith("HTTP/"), required_commands=commands, port_conflicts=ports, passed=not failures, warnings=tuple(warnings), failures=tuple(failures))

    @staticmethod
    def _value(value: str, pattern: str) -> str | None:
        match = re.search(pattern, value, re.MULTILINE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _int_from(value: str, pattern: str) -> int | None:
        match = re.search(pattern, value)
        return int(match.group(1)) if match else None
