"""Phase 3.2 Outline Setup Core security and pipeline tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.integrations.outline_client import OutlineClientConfig
from app.models.outline_setup import OutlineDiscoveryResult, OutlineCredentialInput
from app.security.credential_vault import CredentialVault
from app.security.outline_url_policy import UnsafeOutlineURL, validate_outline_url
from app.services.outline_setup_service import OutlineSetupService
from database.connection import DatabaseManager
from database.models.audit_log import AuditLogORM
from database.models.server import ServerORM
from database.models.user import UserORM


class FakeOutlineClient:
    def __init__(self):
        self.calls = 0

    async def verify_management_api(self, url, credential):
        self.calls += 1
        return OutlineDiscoveryResult(host=url.host, port=url.port, provider_server_id="outline-abc", outline_version="1.10.0", api_compatible=True, existing_key_count=3, metrics_available=True, verified_at=datetime.now(timezone.utc), safe_metadata={"server_name": "Discovered Outline"})


async def _db(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(f"sqlite+aiosqlite:///{tmp_path / 'server32.db'}")
    await db.init()
    async with db.session() as session:
        session.add_all([
            UserORM(telegram_id=882001, full_name="Outline Admin", role="admin", language="en", is_active=True, is_verified=True),
            UserORM(telegram_id=882002, full_name="Other Admin", role="admin", language="my", is_active=True, is_verified=True),
        ])
    return db


@pytest.mark.asyncio
async def test_url_policy_rejects_unsafe_targets_and_allows_explicit_private_mode():
    with pytest.raises(UnsafeOutlineURL):
        await validate_outline_url("file:///tmp/credential")
    with pytest.raises(UnsafeOutlineURL):
        await validate_outline_url("https://10.0.0.8:443/secret", resolve_dns=False)
    private = await validate_outline_url("https://10.0.0.8:443/secret", allow_private=True, resolve_dns=False)
    assert private.host == "10.0.0.8"


@pytest.mark.asyncio
async def test_vault_encrypts_url_and_reference_does_not_expose_secret():
    vault = CredentialVault("phase32-test-secret-which-is-long-enough")
    raw = "https://1.1.1.1:1234/very-secret-path"
    token = vault.encrypt(raw)
    assert raw not in token
    assert vault.decrypt(token) == raw
    assert raw not in CredentialVault.reference(raw)
    assert "very-secret" not in CredentialVault.reference(raw)


@pytest.mark.asyncio
async def test_api_url_and_ssh_inputs_converge_into_same_pipeline(tmp_path):
    db = await _db(tmp_path)
    OutlineSetupService._private_states.clear()
    service = OutlineSetupService(db, client=FakeOutlineClient(), vault=CredentialVault("phase32-test-secret-which-is-long-enough"))
    api_flow = (await service.start_setup(admin_id=882001, setup_method="api_url")).unwrap()
    api_review = await service.validate_and_verify(admin_id=882001, flow_id=api_flow.flow_id, credential=OutlineCredentialInput("https://1.1.1.1:1234/secret", source="api_url"))
    assert api_review.is_success
    api_saved = await service.save_verified(admin_id=882001, flow_id=api_flow.flow_id, name="MG-API", country_code="SG", region="Singapore", enable=False)
    assert api_saved.is_success
    assert api_saved.unwrap().enabled is False

    ssh_flow = (await service.start_setup(admin_id=882001, setup_method="ssh")).unwrap()
    ssh_review = await service.validate_and_verify(admin_id=882001, flow_id=ssh_flow.flow_id, credential=OutlineCredentialInput("https://1.1.1.1:1234/other-secret", source="ssh"))
    assert ssh_review.is_success
    ssh_saved = await service.save_verified(admin_id=882001, flow_id=ssh_flow.flow_id, name="MG-SSH", country_code="JP", region="Tokyo", enable=True)
    assert ssh_saved.is_success
    assert ssh_saved.unwrap().enabled is True
    assert ssh_saved.unwrap().status == ServerORM.STATUS_ONLINE
    await db.close()


@pytest.mark.asyncio
async def test_save_is_atomic_redacted_and_does_not_issue_vpn_key(tmp_path):
    db = await _db(tmp_path)
    OutlineSetupService._private_states.clear()
    client = FakeOutlineClient()
    service = OutlineSetupService(db, client=client, vault=CredentialVault("phase32-test-secret-which-is-long-enough"))
    flow = (await service.start_setup(admin_id=882001, setup_method="api_url")).unwrap()
    raw = "https://1.1.1.1:1234/super-secret-token"
    assert (await service.validate_and_verify(admin_id=882001, flow_id=flow.flow_id, credential=OutlineCredentialInput(raw, source="api_url"))).is_success
    saved = await service.save_verified(admin_id=882001, flow_id=flow.flow_id, name="MG-Redacted", country_code="US", region="Virginia", enable=False)
    assert saved.is_success
    async with db.session() as session:
        row = (await session.execute(select(ServerORM).where(ServerORM.public_server_id == saved.unwrap().server_public_id))).scalar_one()
        audit = (await session.execute(select(AuditLogORM).where(AuditLogORM.action == "server.outline_connected"))).scalar_one()
        assert row.api_url is None
        assert row.credential_ciphertext and raw not in row.credential_ciphertext
        assert row.secret_reference and raw not in row.secret_reference
        assert row.status == ServerORM.STATUS_DISABLED
        assert row.health_status == ServerORM.HEALTH_OK
        assert row.enabled is False
        assert raw not in (audit.new_value or "")
    assert client.calls == 1
    await db.close()


@pytest.mark.asyncio
async def test_setup_session_is_owned_and_expiry_is_enforced(tmp_path):
    db = await _db(tmp_path)
    OutlineSetupService._private_states.clear()
    service = OutlineSetupService(db, client=FakeOutlineClient(), vault=CredentialVault("phase32-test-secret-which-is-long-enough"))
    flow = (await service.start_setup(admin_id=882001, setup_method="api_url")).unwrap()
    denied = await service.validate_and_verify(admin_id=882002, flow_id=flow.flow_id, credential=OutlineCredentialInput("https://1.1.1.1:1234/secret"))
    assert denied.error.code == "setup_expired"
    service._private_states[flow.flow_id]["session"] = flow.__class__(flow_id=flow.flow_id, admin_id=flow.admin_id, setup_method=flow.setup_method, existing_server_id=flow.existing_server_id, created_at=flow.created_at, expires_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
    expired = await service.validate_and_verify(admin_id=882001, flow_id=flow.flow_id, credential=OutlineCredentialInput("https://1.1.1.1:1234/secret"))
    assert expired.error.code == "setup_expired"
    await db.close()
