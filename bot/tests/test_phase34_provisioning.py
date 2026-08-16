from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.result import Success
from app.integrations.outline_installer import OutlineInstaller
from app.models.outline_setup import OutlineSetupSession
from app.models.provisioning import ProvisioningPolicy, ProvisioningStatus
from app.models.ssh_discovery import SSHCredentialInput
from app.services.outline_provisioning_service import OutlineProvisioningService


class FakeSetup:
    def __init__(self):
        self.sessions = {}
        self.credentials = []

    async def start_setup(self, *, admin_id, setup_method, existing_server_id=None):
        now = datetime.now(timezone.utc)
        flow = OutlineSetupSession("flow-1", admin_id, setup_method, None, now, now.replace(year=now.year + 1))
        self.sessions[flow.flow_id] = flow
        return Success(flow)

    async def validate_and_verify(self, *, admin_id, flow_id, credential, allow_private=False):
        self.credentials.append(credential)
        return Success(object())

    def cancel_setup(self, *, admin_id, flow_id):
        return True


class FakeSSH:
    async def discover(self, credential):
        class Discovery:
            outline_found = False
            management_url = None
        return Discovery()

    async def run_preflight(self, credential, policy):
        return {
            "os_release": 'PRETTY_NAME="Ubuntu 24.04 LTS"',
            "uname": "x86_64\n",
            "identity": "0\nroot",
            "docker": "Docker version 26",
            "disk": "/dev/root 20000000 5000000 15000000 25% /\n",
            "memory": "2048\n",
            "commands": "sh\ncurl\ngetent\nss",
            "dns": "140.82.112.4 github.com",
            "https": "HTTP/2 200",
            "ports": "LISTEN 0 128 0.0.0.0:22",
        }

    async def run_installer(self, credential, command, *, timeout_seconds):
        return 0, 'apiUrl: https://10.0.0.1:12345/secret\ncertSha256: abc123', ''


@pytest.fixture
def service():
    return OutlineProvisioningService(outline_setup=FakeSetup(), ssh=FakeSSH(), policy=ProvisioningPolicy())


def credential():
    return SSHCredentialInput(host="203.0.113.10", port=22, username="root", auth_method="password", password="secret", expected_host_key_fingerprint="SHA256:abc")


@pytest.mark.asyncio
async def test_preflight_passes_but_install_requires_confirmation(service):
    started = await service.start(admin_id=7, credential=credential())
    assert started.is_success
    flow_id = started.unwrap().flow_id
    plan = await service.preflight(admin_id=7, flow_id=flow_id)
    assert plan.is_success
    assert plan.unwrap().requires_confirmation is True
    blocked = await service.install(admin_id=7, flow_id=flow_id)
    assert blocked.error.code == "confirmation_required"


@pytest.mark.asyncio
async def test_confirmation_is_one_time_and_install_hands_off_to_setup(service):
    started = await service.start(admin_id=7, credential=credential())
    flow_id = started.unwrap().flow_id
    await service.preflight(admin_id=7, flow_id=flow_id)
    token = service.confirmation_token(admin_id=7, flow_id=flow_id)
    assert token
    confirmed = service.confirm(admin_id=7, flow_id=flow_id, token=token)
    assert confirmed.is_success
    installed = await service.install(admin_id=7, flow_id=flow_id)
    assert installed.is_success
    assert service.outline_setup.credentials[0].source == "auto_provision"
    assert service.outline_setup.credentials[0].management_url.endswith("/secret")
    duplicate = await service.install(admin_id=7, flow_id=flow_id)
    assert duplicate.error.code in {"already_installing", "provisioning_expired", "confirmation_required"}


def test_installer_repr_does_not_leak_credentials():
    result = OutlineInstaller().parse_result("apiUrl: https://10.0.0.1:12345/secret certSha256: private", host="203.0.113.10", strategy="test")
    assert result.success
    assert "10.0.0.1" not in repr(result)
    assert "private" not in repr(result)
