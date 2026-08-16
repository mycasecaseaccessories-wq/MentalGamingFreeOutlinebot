"""Typed state and result models for safe Outline Auto-Provisioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .ssh_discovery import SSHCredentialInput


class ProvisioningStatus(StrEnum):
    STARTED = "started"
    SSH_READY = "ssh_ready"
    PREFLIGHT_PASSED = "preflight_passed"
    EXISTING_OUTLINE_FOUND = "existing_outline_found"
    AWAITING_CONFIRMATION = "awaiting_install_confirmation"
    INSTALLING = "installing"
    INSTALLED_PENDING_VERIFICATION = "installed_pending_verification"
    VERIFICATION_FAILED = "verification_failed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ProvisioningPolicy:
    min_disk_mb: int = 2048
    min_memory_mb: int = 1024
    supported_architectures: tuple[str, ...] = ("x86_64", "amd64", "aarch64", "arm64")
    supported_os_tokens: tuple[str, ...] = ("ubuntu", "debian")
    preflight_timeout_seconds: float = 30.0
    install_timeout_seconds: float = 900.0
    command_timeout_seconds: float = 20.0
    installer_strategy: str = "official-outline-bootstrap-v1"
    installer_url: str = "https://raw.githubusercontent.com/Jigsaw-Code/outline-server/master/src/server_manager/install_scripts/install_server.sh"


@dataclass(frozen=True, slots=True)
class PreflightResult:
    host: str
    os_name: str | None
    architecture: str | None
    privilege_mode: str
    docker_available: bool
    disk_free_mb: int | None
    memory_available_mb: int | None
    dns_ok: bool
    https_ok: bool
    required_commands: tuple[str, ...]
    port_conflicts: tuple[int, ...]
    passed: bool
    warnings: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProvisioningPlan:
    flow_id: str
    host: str
    preflight: PreflightResult
    installer_strategy: str
    installer_version: str
    expected_changes: tuple[str, ...]
    warnings: tuple[str, ...]
    requires_confirmation: bool = True


@dataclass(frozen=True, slots=True)
class OutlineProvisionResult:
    success: bool
    management_url: str | None = field(repr=False, default=None)
    cert_sha256: str | None = field(repr=False, default=None)
    installation_version: str | None = None
    installation_type: str | None = None
    safe_metadata: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    status: ProvisioningStatus = ProvisioningStatus.FAILED
    diagnostics: str | None = None


@dataclass(frozen=True, slots=True)
class ProvisioningSession:
    flow_id: str
    admin_id: int
    credential: SSHCredentialInput = field(repr=False)
    created_at: datetime
    expires_at: datetime
    status: ProvisioningStatus = ProvisioningStatus.STARTED
    plan: ProvisioningPlan | None = None
    confirmation_nonce: str | None = field(repr=False, default=None)
    install_started: bool = False
