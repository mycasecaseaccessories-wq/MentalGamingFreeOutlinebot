"""Async-safe, read-only SSH discovery provider for Phase 3.3."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import asyncssh

from app.models.ssh_discovery import OutlineSSHDiscoveryResult, SSHCredentialInput, SSHHostKey


class SSHDiscoveryError(RuntimeError):
    pass


class OutlineNotFound(SSHDiscoveryError):
    pass


@dataclass(frozen=True, slots=True)
class SSHProviderConfig:
    connect_timeout_seconds: float = 10.0
    command_timeout_seconds: float = 8.0
    setup_total_timeout_seconds: float = 45.0
    known_hosts: str | None = None


class _FingerprintSSHClient(asyncssh.SSHClient):
    def __init__(self, expected: str | None) -> None:
        self.expected = expected
        self.host_key: SSHHostKey | None = None

    def validate_host_public_key(self, host: str, addr: str, port: int, key: asyncssh.SSHKey) -> bool:
        fingerprint = key.get_fingerprint("sha256")
        self.host_key = SSHHostKey(host=host, port=port, fingerprint=fingerprint, algorithm=key.get_algorithm())
        if not self.expected:
            return False
        return fingerprint == self.expected


class SSHDiscoveryProvider:
    """Only opens an SSH session and executes fixed read-only discovery commands."""

    READ_ONLY_COMMANDS = {
        "os_release": "cat /etc/os-release 2>/dev/null",
        "uname": "uname -a 2>/dev/null",
        "docker_ps": "docker ps --format '{{json .}}' 2>/dev/null",
        "docker_inspect": "docker ps -q 2>/dev/null | head -20 | xargs -r docker inspect --format '{{json .Config.Env}}|{{json .Config.Labels}}' 2>/dev/null",
        "outline_config": "for f in /opt/outline/access.txt /opt/outline/config.yml /etc/outline/access.txt /etc/outline/config.yml; do if [ -r \"$f\" ]; then printf '\\n---FILE:%s---\\n' \"$f\"; cat \"$f\"; fi; done",
        "systemd": "systemctl is-active outline-server 2>/dev/null; systemctl is-active shadowbox 2>/dev/null",
    }

    def __init__(self, config: SSHProviderConfig | None = None) -> None:
        self.config = config or SSHProviderConfig()

    async def inspect_host_key(self, credential: SSHCredentialInput) -> SSHHostKey:
        client = _FingerprintSSHClient(credential.expected_host_key_fingerprint)
        try:
            async with asyncssh.connect(credential.host, port=credential.port, username=credential.username, password=credential.password, client_keys=[credential.private_key] if credential.private_key else None, passphrase=credential.key_passphrase, known_hosts=self.config.known_hosts, client_factory=lambda: client, connect_timeout=self.config.connect_timeout_seconds) as conn:
                key = conn.get_server_host_key()
                return SSHHostKey(host=credential.host, port=credential.port, fingerprint=key.get_fingerprint("sha256"), algorithm=key.get_algorithm())
        except asyncssh.KeyExchangeFailed as exc:
            raise SSHDiscoveryError("SSH host key verification failed.") from exc
        except asyncssh.PermissionDenied as exc:
            raise SSHDiscoveryError("SSH authentication failed.") from exc
        except (asyncssh.Error, OSError, asyncio.TimeoutError) as exc:
            raise SSHDiscoveryError("SSH connection failed.") from exc

    async def discover(self, credential: SSHCredentialInput) -> OutlineSSHDiscoveryResult:
        if not credential.expected_host_key_fingerprint and not self.config.known_hosts:
            raise SSHDiscoveryError("An SSH host-key fingerprint or known-hosts policy is required.")
        try:
            return await asyncio.wait_for(self._discover(credential), timeout=self.config.setup_total_timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise SSHDiscoveryError("SSH discovery timed out.") from exc

    async def _discover(self, credential: SSHCredentialInput) -> OutlineSSHDiscoveryResult:
        client = _FingerprintSSHClient(credential.expected_host_key_fingerprint)
        try:
            async with asyncssh.connect(credential.host, port=credential.port, username=credential.username, password=credential.password, client_keys=[credential.private_key] if credential.private_key else None, passphrase=credential.key_passphrase, known_hosts=self.config.known_hosts, client_factory=lambda: client, connect_timeout=self.config.connect_timeout_seconds) as conn:
                outputs: dict[str, str] = {}
                for name, command in self.READ_ONLY_COMMANDS.items():
                    result = await asyncio.wait_for(conn.run(command, check=False), timeout=self.config.command_timeout_seconds)
                    outputs[name] = (result.stdout or "")[:65536]
                return self._parse(credential.host, credential.port, outputs)
        except asyncssh.PermissionDenied as exc:
            raise SSHDiscoveryError("SSH authentication failed.") from exc
        except asyncssh.KeyExchangeFailed as exc:
            raise SSHDiscoveryError("SSH host key verification failed.") from exc
        except (asyncssh.Error, OSError) as exc:
            raise SSHDiscoveryError("SSH discovery connection failed.") from exc

    def _parse(self, host: str, port: int, outputs: dict[str, str]) -> OutlineSSHDiscoveryResult:
        os_name = self._parse_os(outputs.get("os_release", ""))
        architecture = self._parse_arch(outputs.get("uname", ""))
        combined = "\n".join(outputs.values())
        outline_marked = bool(re.search(r"(?i)outline|shadowbox", combined))
        management_url = self._find_url(combined)
        cert_sha256 = self._find_value(combined, ("certSha256", "cert_sha256", "certificateSha256"))
        provider_id = self._find_value(combined, ("serverId", "server_id", "provider_server_id"))
        if not outline_marked and not management_url:
            return OutlineSSHDiscoveryResult(host=host, port=port, os_name=os_name, architecture=architecture, outline_found=False, management_url=None, cert_sha256=None, provider_server_id=None, installation_type=None, safe_metadata={"os_name": os_name, "architecture": architecture})
        return OutlineSSHDiscoveryResult(host=host, port=port, os_name=os_name, architecture=architecture, outline_found=True, management_url=management_url, cert_sha256=cert_sha256, provider_server_id=provider_id, installation_type="docker" if "docker" in outputs.get("docker_ps", "").lower() else "service", safe_metadata={"os_name": os_name, "architecture": architecture, "active_service": self._active_service(outputs.get("systemd", ""))})

    @staticmethod
    def _parse_os(value: str) -> str | None:
        name = re.search(r'^PRETTY_NAME=["\']?([^"\'\n]+)', value, re.MULTILINE)
        return name.group(1).strip()[:80] if name else None

    @staticmethod
    def _parse_arch(value: str) -> str | None:
        parts = value.split()
        return parts[-1][:32] if parts else None

    @staticmethod
    def _find_url(value: str) -> str | None:
        match = re.search(r"https?://[^\s\"'<>|]+", value)
        return match.group(0).rstrip(";,)") if match else None

    @staticmethod
    def _find_value(value: str, keys: tuple[str, ...]) -> str | None:
        for key in keys:
            match = re.search(rf"(?i)(?:{re.escape(key)})\s*[:=]\s*[\"']?([^\s\"'|,}}]+)", value)
            if match: return match.group(1)[:256]
        return None

    @staticmethod
    def _active_service(value: str) -> str | None:
        for name in ("outline-server", "shadowbox"):
            if re.search(rf"active\s+{re.escape(name)}", value, re.I) or value.strip() == "active": return name
        return None
