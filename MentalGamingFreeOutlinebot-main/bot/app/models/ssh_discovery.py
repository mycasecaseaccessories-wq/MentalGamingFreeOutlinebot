"""Typed, non-secret DTOs for existing-VPS SSH discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.models.outline_setup import OutlineSetupReview


AuthMethod = Literal["password", "private_key"]


@dataclass(frozen=True, slots=True)
class SSHCredentialInput:
    host: str
    port: int
    username: str
    auth_method: AuthMethod
    password: str | None = None
    private_key: str | None = None
    key_passphrase: str | None = None
    expected_host_key_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class SSHHostKey:
    host: str
    port: int
    fingerprint: str
    algorithm: str


@dataclass(frozen=True, slots=True)
class OutlineSSHDiscoveryResult:
    host: str
    port: int
    os_name: str | None
    architecture: str | None
    outline_found: bool
    management_url: str | None
    cert_sha256: str | None
    provider_server_id: str | None
    installation_type: str | None
    safe_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_handoff_credential(self) -> bool:
        return bool(self.outline_found and self.management_url)


@dataclass(frozen=True, slots=True)
class SSHDiscoveryHandoff:
    discovery: OutlineSSHDiscoveryResult
    outline_review: OutlineSetupReview
