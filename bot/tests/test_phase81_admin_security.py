from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.admin_security import AdminPrincipalStatus, AdminRole
from app.services.admin_authorization_service import AdminAuthorizationService
from database.connection import DatabaseManager
from database.models.admin_security import (
    AdminPrincipalORM,
    PrivilegedActionChallengeORM,
    SecurityEventORM,
)
from database.models.audit_log import AuditLogORM
from database.models.user import UserORM


def _url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'phase81.db'}"


@pytest.fixture
async def security_service(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    async with db.session() as session:
        session.add_all(
            [
                UserORM(telegram_id=100, full_name="Owner", role="admin"),
                UserORM(telegram_id=200, full_name="Support", role="admin"),
                UserORM(telegram_id=300, full_name="Customer", role="customer"),
            ]
        )
    service = AdminAuthorizationService(db)
    yield service
    await db.close()
    DatabaseManager._instance = None


@pytest.mark.asyncio
async def test_bootstrap_is_authoritative_and_customer_is_denied(security_service):
    service = security_service
    owner = await service.ensure_bootstrap_admin(100, {100})
    assert owner is not None
    assert owner.role == AdminRole.OWNER.value
    assert (await service.authorize(300)).is_failure
    assert (await service.authorize(200)).is_success

    await service.change_status(100, 200, AdminPrincipalStatus.REVOKED.value, reason="offboarding")
    assert (await service.authorize(200, "manage_servers")).is_failure
    # The configured bootstrap ID cannot resurrect a revoked principal.
    restored = await service.ensure_bootstrap_admin(200, {200})
    assert restored is not None
    assert restored.status == AdminPrincipalStatus.REVOKED.value
    assert (await service.authorize(200)).is_failure


@pytest.mark.asyncio
async def test_privilege_scope_and_final_owner_invariant(security_service):
    service = security_service
    await service.ensure_bootstrap_admin(100, {100})
    await service.resolve_principal(200)

    denied = await service.change_role(200, 100, AdminRole.OWNER.value)
    assert denied.error is not None
    assert denied.error.code in {"permission_denied", "role_scope_denied"}

    self_escalation = await service.change_role(100, 100, AdminRole.SUPER_ADMIN.value)
    assert self_escalation.error is not None
    assert self_escalation.error.code == "role_scope_denied"

    last_owner = await service.change_status(
        100, 100, AdminPrincipalStatus.REVOKED.value, reason="must not lock out recovery"
    )
    assert last_owner.error is not None
    assert last_owner.error.code == "last_owner_protected"


@pytest.mark.asyncio
async def test_confirmation_is_bound_single_use_and_cross_admin_safe(security_service):
    service = security_service
    await service.ensure_bootstrap_admin(100, {100})
    await service.resolve_principal(200)

    created = await service.create_challenge(
        100,
        action_type="admin.revoke",
        permission="manage_admins",
        target_type="admin_principal",
        target_safe_id="apr_target",
        payload={"reason": "security review"},
        chat_type="private",
    )
    assert created.is_success
    challenge = created.unwrap()

    cross_admin = await service.consume_challenge(
        200,
        public_id=challenge.public_id,
        action_type="admin.revoke",
        permission="manage_admins",
        target_type="admin_principal",
        target_safe_id="apr_target",
        payload={"reason": "security review"},
        chat_type="private",
    )
    assert cross_admin.error is not None

    consumed = await service.consume_challenge(
        100,
        public_id=challenge.public_id,
        action_type="admin.revoke",
        permission="manage_admins",
        target_type="admin_principal",
        target_safe_id="apr_target",
        payload={"reason": "security review"},
        chat_type="private",
    )
    assert consumed.is_success
    async with service.db.session() as session:
        audits = (await session.execute(select(AuditLogORM))).scalars().all()
        assert any(audit.action == "critical_action.executed" for audit in audits)

    replay = await service.consume_challenge(
        100,
        public_id=challenge.public_id,
        action_type="admin.revoke",
        permission="manage_admins",
        target_type="admin_principal",
        target_safe_id="apr_target",
        payload={"reason": "security review"},
        chat_type="private",
    )
    assert replay.error is not None
    assert replay.error.code == "challenge_used"


@pytest.mark.asyncio
async def test_admin_session_validation_and_revocation(security_service):
    service = security_service
    await service.ensure_bootstrap_admin(100, {100})
    await service.resolve_principal(200)

    opened = await service.open_session(200, ttl_seconds=120, chat_id=200)
    assert opened.is_success
    session = opened.unwrap()
    assert session.token
    assert (await service.validate_session(session.token)).is_success

    revoked = await service.change_status(
        100, 200, AdminPrincipalStatus.REVOKED.value, reason="offboarding"
    )
    assert revoked.is_success
    invalidated = await service.validate_session(session.token)
    assert invalidated.error is not None
    assert invalidated.error.code == "session_revoked"


@pytest.mark.asyncio
async def test_expired_challenge_and_security_events_are_safe(security_service):
    service = security_service
    await service.ensure_bootstrap_admin(100, {100})
    created = await service.create_challenge(
        100,
        action_type="admin.lock",
        permission="manage_admins",
        target_type="admin_principal",
        target_safe_id="apr_target",
        payload={},
        chat_type="private",
    )
    challenge = created.unwrap()
    async with service.db.session() as session:
        row = (
            await session.execute(
                select(PrivilegedActionChallengeORM).where(
                    PrivilegedActionChallengeORM.public_id == challenge.public_id
                )
            )
        ).scalar_one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    expired = await service.consume_challenge(
        100,
        public_id=challenge.public_id,
        action_type="admin.lock",
        permission="manage_admins",
        target_type="admin_principal",
        target_safe_id="apr_target",
        payload={},
        chat_type="private",
    )
    assert expired.error is not None
    assert expired.error.code == "challenge_expired"

    async with service.db.session() as session:
        events = (await session.execute(select(SecurityEventORM))).scalars().all()
        audits = (await session.execute(select(AuditLogORM))).scalars().all()
        assert events
        assert audits
        assert all("token" not in (event.metadata_json or "").lower() for event in events)
        assert all("password" not in (event.metadata_json or "").lower() for event in events)
        principal = (await session.execute(select(AdminPrincipalORM))).scalars().first()
        assert principal is not None
