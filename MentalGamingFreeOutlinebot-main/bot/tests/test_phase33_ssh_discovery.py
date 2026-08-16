"""Phase 3.3 SSH discovery and Phase 3.2 handoff tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.result import Success
from app.integrations.ssh_provider import SSHDiscoveryProvider, SSHProviderConfig
from app.models.outline_setup import OutlineDiscoveryResult, OutlineSetupReview, OutlineSetupSession
from app.models.ssh_discovery import OutlineSSHDiscoveryResult, SSHCredentialInput
from app.services.ssh_discovery_service import SSHDiscoveryService
from app.security.ssh_policy import UnsafeSSHTarget, validate_ssh_input


class FakeOutlineSetup:
    def __init__(self):
        self.calls = []
        self.cancelled = []

    async def start_setup(self, *, admin_id, setup_method, existing_server_id=None):
        now = datetime.now(timezone.utc)
        return Success(OutlineSetupSession(flow_id="flow-33", admin_id=admin_id, setup_method=setup_method, existing_server_id=existing_server_id, created_at=now, expires_at=now.replace(year=now.year + 1)))

    async def validate_and_verify(self, *, admin_id, flow_id, credential, allow_private=False):
        self.calls.append(credential)
        discovery = OutlineDiscoveryResult(host="1.1.1.1", port=8443, provider_server_id="srv", outline_version="1.10", api_compatible=True, existing_key_count=2, metrics_available=False, verified_at=datetime.now(timezone.utc), safe_metadata={"server_name": "Found Outline"})
        return Success(OutlineSetupReview(flow_id=flow_id, server_public_id=None, source=credential.source, discovery=discovery, name=None, country_code=None, region=None, paid_enabled=False, free_trial_enabled=False, vip_enabled=False, max_users=None, traffic_limit_bytes=None, priority=100, weight=1, credential_reference="outline:v1:test"))

    def cancel_setup(self, *, admin_id, flow_id):
        self.cancelled.append((admin_id, flow_id))
        return True


class FakeSSHProvider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def discover(self, credential):
        self.calls.append(credential)
        return self.result


@pytest.mark.asyncio
async def test_read_only_command_allowlist_has_no_install_or_mutation_command():
    commands = " ".join(SSHDiscoveryProvider.READ_ONLY_COMMANDS.values()).lower()
    for forbidden in ("apt install", "yum install", "dnf install", "docker pull", "docker run", "curl | sh", "wget | sh", "iptables", "ufw", "reboot", "shutdown", "useradd"):
        assert forbidden not in commands


def test_discovery_parser_finds_outline_credentials_without_returning_raw_output():
    provider = SSHDiscoveryProvider(SSHProviderConfig())
    result = provider._parse("1.1.1.1", 22, {
        "os_release": 'PRETTY_NAME="Ubuntu 24.04 LTS"',
        "uname": "Linux host x86_64",
        "docker_ps": '{"Image":"quay.io/outline/shadowbox:latest","Names":"shadowbox"}',
        "docker_inspect": 'apiUrl=https://1.1.1.1:8443/secret-token|certSha256=ABCDEF|serverId=outline-1',
        "outline_config": "",
        "systemd": "active shadowbox",
    })
    assert result.outline_found is True
    assert result.management_url == "https://1.1.1.1:8443/secret-token"
    assert result.cert_sha256 == "ABCDEF"
    assert result.safe_metadata["os_name"] == "Ubuntu 24.04 LTS"


def test_discovery_parser_returns_not_found_without_installing():
    provider = SSHDiscoveryProvider()
    result = provider._parse("203.0.113.11", 22, {"os_release": "PRETTY_NAME=Debian", "uname": "Linux host aarch64", "docker_ps": "", "docker_inspect": "", "outline_config": "", "systemd": "inactive"})
    assert result.outline_found is False
    assert result.management_url is None


def test_ssh_policy_rejects_private_without_explicit_mode_and_accepts_public():
    with pytest.raises(UnsafeSSHTarget):
        validate_ssh_input(SSHCredentialInput("10.0.0.5", 22, "ubuntu", "password", password="secret"))
    value = validate_ssh_input(SSHCredentialInput("1.1.1.1", 2222, "ubuntu", "password", password="secret"))
    assert value.port == 2222


@pytest.mark.asyncio
async def test_existing_outline_hands_off_once_to_phase32_and_clears_ssh_secret():
    outline = FakeOutlineSetup()
    discovery = OutlineSSHDiscoveryResult(host="1.1.1.1", port=22, os_name="Ubuntu", architecture="x86_64", outline_found=True, management_url="https://1.1.1.1:8443/secret-token", cert_sha256="ABC", provider_server_id="outline-1", installation_type="docker", safe_metadata={})
    provider = FakeSSHProvider(discovery)
    service = SSHDiscoveryService(db=object(), provider=provider, outline_setup=outline)
    flow = (await service.start_setup(admin_id=99)).unwrap()
    service._states[flow]["credential"] = SSHCredentialInput("1.1.1.1", 22, "ubuntu", "password", password="very-secret")
    result = await service.discover_stored(admin_id=99, flow_id=flow)
    assert result.is_success
    assert outline.calls[0].source == "ssh"
    assert outline.calls[0].management_url.endswith("secret-token")
    assert flow not in service._states


@pytest.mark.asyncio
async def test_outline_not_found_is_not_a_provisioning_success():
    outline = FakeOutlineSetup()
    provider = FakeSSHProvider(OutlineSSHDiscoveryResult(host="1.1.1.2", port=22, os_name="Ubuntu", architecture="x86_64", outline_found=False, management_url=None, cert_sha256=None, provider_server_id=None, installation_type=None, safe_metadata={}))
    service = SSHDiscoveryService(db=object(), provider=provider, outline_setup=outline)
    flow = (await service.start_setup(admin_id=99)).unwrap()
    service._states[flow]["credential"] = SSHCredentialInput("1.1.1.2", 22, "ubuntu", "password", password="secret")
    result = await service.discover_stored(admin_id=99, flow_id=flow)
    assert result.is_success
    assert result.unwrap().outline_found is False
    assert outline.calls == []
    assert outline.cancelled == [(99, flow)]
