"""Centrally controlled Outline installer strategy and redacted result parser."""

from __future__ import annotations

import re
import shlex

from app.models.provisioning import OutlineProvisionResult, ProvisioningPolicy, ProvisioningStatus


class InstallerPolicyError(ValueError):
    pass


class OutlineInstaller:
    """Builds one approved installer command; never accepts Telegram input."""

    URL_PATTERN = re.compile(r"^https://[A-Za-z0-9._/-]+/install_server\.sh$")

    def build_command(self, policy: ProvisioningPolicy, *, use_sudo: bool) -> str:
        if not self.URL_PATTERN.fullmatch(policy.installer_url):
            raise InstallerPolicyError("Installer source is not an approved HTTPS Outline script.")
        source = shlex.quote(policy.installer_url)
        privilege = "sudo -n " if use_sudo else ""
        return f"curl --proto '=https' --tlsv1.2 -fsSL --max-time 60 {source} | {privilege}bash -s -- --no-prompt"

    def parse_result(self, stdout: str, *, host: str, strategy: str) -> OutlineProvisionResult:
        # Parse only required fields in memory. Never include stdout in repr/logs.
        url = self._find(stdout, ("apiUrl", "api_url", "managementApiUrl", "management_api_url"))
        if url is None:
            match = re.search(r"https://[^\s\"'<>|]+", stdout)
            url = match.group(0).rstrip(";,)\"") if match else None
        cert = self._find(stdout, ("certSha256", "cert_sha256", "certificateSha256"))
        provider_id = self._find(stdout, ("serverId", "server_id", "provider_server_id"))
        version = self._find(stdout, ("version", "outlineVersion", "outline_version"))
        if not url:
            return OutlineProvisionResult(success=False, status=ProvisioningStatus.VERIFICATION_FAILED, diagnostics="Installer completed without a management API credential.")
        return OutlineProvisionResult(success=True, management_url=url, cert_sha256=cert, installation_version=version, installation_type="official", safe_metadata={"host": host, "strategy": strategy, "provider_server_id": provider_id or ""}, status=ProvisioningStatus.INSTALLED_PENDING_VERIFICATION)

    @staticmethod
    def _find(value: str, keys: tuple[str, ...]) -> str | None:
        for key in keys:
            match = re.search(rf"(?i){re.escape(key)}\s*[:=]\s*[\"']?([^\s\"'|,}}]+)", value)
            if match:
                return match.group(1)[:256]
        return None
