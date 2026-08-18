"""Centralized, database-authoritative admin authorization for Phase 8.1."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update

from app.core.exceptions import PermissionDeniedException
from app.core.result import Result, ResultError
from app.events import EventType, bus
from app.models.admin_security import (
    ADMIN_PERMISSION_KEYS,
    CRITICAL_ACTIONS,
    ROLE_PERMISSION_POLICY,
    ROLE_RANK,
    AdminPrincipalStatus,
    AdminRole,
    SecurityEventType,
)
from app.models.enums import Permission, UserRole
from app.observability import get_request_id, request_ctx
from config import settings
from database.models.admin_security import (
    AdminPermissionGrantORM,
    AdminPrincipalORM,
    AdminSessionORM,
    PrivilegedActionChallengeORM,
    SecurityEventORM,
)
from database.models.audit_log import AuditLogORM
from database.models.user import UserORM

_ALL_PERMISSION_KEYS = frozenset(item.value for item in Permission) | ADMIN_PERMISSION_KEYS


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    id: int
    public_id: str
    user_id: int
    telegram_id: int
    status: str
    role: str
    session_version: int
    permissions: frozenset[str]


@dataclass(frozen=True, slots=True)
class AdminSession:
    public_id: str
    token: str
    principal_id: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ConfirmationChallenge:
    public_id: str
    action_type: str
    target_type: str | None
    target_safe_id: str | None
    expires_at: datetime


class AdminAuthorizationService:
    """The only runtime authority for privileged Admin decisions."""

    DEFAULT_CONFIRMATION_TTL_SECONDS = 300

    def __init__(self, db: Any, *, confirmation_ttl_seconds: int | None = None) -> None:
        self.db = db
        configured_ttl = (
            confirmation_ttl_seconds
            if confirmation_ttl_seconds is not None
            else settings.admin_confirmation_ttl_seconds
        )
        self.confirmation_ttl_seconds = max(60, min(int(configured_ttl), 900))
        self.chat_policy = settings.admin_chat_policy
        self.approved_chat_ids = frozenset(settings.admin_approved_chat_ids)

    @staticmethod
    def _digest(payload: dict[str, Any] | None) -> str:
        canonical = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _failure(code: str, message: str) -> Result[Any]:
        return Result(error=ResultError(code=code, message=message))

    @staticmethod
    def _principal(
        principal: AdminPrincipalORM,
        user: UserORM,
        permissions: set[str],
    ) -> AdminPrincipal:
        return AdminPrincipal(
            id=principal.id,
            public_id=principal.public_id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            status=principal.status,
            role=principal.role,
            session_version=principal.session_version,
            permissions=frozenset(permissions),
        )

    async def list_admins(self, *, limit: int = 20, offset: int = 0) -> list[AdminPrincipal]:
        async with self.db.session() as session:
            rows = (
                await session.execute(
                    select(AdminPrincipalORM, UserORM)
                    .join(UserORM, UserORM.id == AdminPrincipalORM.user_id)
                    .order_by(AdminPrincipalORM.id.asc())
                    .limit(max(1, min(limit, 100)))
                    .offset(max(0, offset))
                )
            ).all()
            result: list[AdminPrincipal] = []
            for principal, user in rows:
                result.append(
                    self._principal(principal, user, await self._permissions(session, principal))
                )
            return result

    async def list_audit(self, *, limit: int = 20) -> list[dict[str, Any]]:
        async with self.db.session() as session:
            rows = (
                (
                    await session.execute(
                        select(AuditLogORM)
                        .order_by(AuditLogORM.id.desc())
                        .limit(max(1, min(limit, 100)))
                    )
                )
                .scalars()
                .all()
            )
            return [
                {
                    "action": row.action,
                    "entity_type": row.entity_type,
                    "entity_id": row.entity_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "note": row.note,
                }
                for row in rows
            ]

    async def open_session(
        self,
        telegram_id: int,
        *,
        ttl_seconds: int = 1800,
        chat_id: int | None = None,
    ) -> Result[AdminSession]:
        try:
            principal = await self.require_admin(telegram_id)
        except PermissionDeniedException:
            return self._failure("admin_access_denied", "Action not permitted.")
        now = datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        row = AdminSessionORM(
            public_id=f"ase_{uuid4().hex[:24]}",
            principal_id=principal.id,
            token_digest=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            session_version=principal.session_version,
            created_at=now,
            expires_at=now + timedelta(seconds=max(60, min(ttl_seconds, 86400))),
            last_seen_at=now,
            chat_id=chat_id,
            request_id=get_request_id() or None,
        )
        async with self.db.session() as session:
            session.add(row)
            await session.flush()
        return Result(
            value=AdminSession(
                public_id=row.public_id,
                token=token,
                principal_id=row.principal_id,
                expires_at=row.expires_at,
            )
        )

    async def validate_session(self, token: str) -> Result[AdminPrincipal]:
        if not token or len(token) < 20:
            return self._failure("session_invalid", "Action not permitted.")
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(AdminSessionORM)
                    .where(AdminSessionORM.token_digest == digest)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None or row.revoked_at is not None:
                return self._failure("session_invalid", "Action not permitted.")
            expires_at = row.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= now:
                return self._failure("session_expired", "Action not permitted.")
            pair = (
                await session.execute(
                    select(AdminPrincipalORM, UserORM)
                    .join(UserORM, UserORM.id == AdminPrincipalORM.user_id)
                    .where(AdminPrincipalORM.id == row.principal_id)
                    .with_for_update()
                )
            ).one_or_none()
            if pair is None:
                return self._failure("session_invalid", "Action not permitted.")
            principal, user = pair
            if (
                principal.status != AdminPrincipalStatus.ACTIVE.value
                or principal.session_version != row.session_version
            ):
                return self._failure("session_revoked", "Action not permitted.")
            row.last_seen_at = now
            return Result(
                value=self._principal(principal, user, await self._permissions(session, principal))
            )

    async def revoke_session(self, telegram_id: int, public_id: str) -> Result[bool]:
        try:
            principal = await self.require_admin(telegram_id)
        except PermissionDeniedException:
            return self._failure("admin_access_denied", "Action not permitted.")
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(AdminSessionORM)
                    .where(
                        AdminSessionORM.public_id == public_id,
                        AdminSessionORM.principal_id == principal.id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                return self._failure("session_not_found", "Action not permitted.")
            row.revoked_at = datetime.now(UTC)
            return Result(value=True)

    async def ensure_bootstrap_admin(
        self,
        telegram_id: int,
        configured_admin_ids: set[int] | frozenset[int] | list[int] | tuple[int, ...],
    ) -> AdminPrincipal | None:
        """Consume the legacy allowlist only to establish initial DB authority."""
        if telegram_id not in set(configured_admin_ids):
            return await self.resolve_principal(telegram_id)
        async with self.db.session() as session:
            user = (
                await session.execute(select(UserORM).where(UserORM.telegram_id == telegram_id))
            ).scalar_one_or_none()
            if user is None:
                return None
            principal = (
                await session.execute(
                    select(AdminPrincipalORM).where(AdminPrincipalORM.user_id == user.id)
                )
            ).scalar_one_or_none()
            if principal is None:
                principal = AdminPrincipalORM(
                    public_id=f"apr_{uuid4().hex[:24]}",
                    user_id=user.id,
                    status=AdminPrincipalStatus.ACTIVE.value,
                    role=AdminRole.OWNER.value,
                    created_by=telegram_id,
                    bootstrap_source="config_bootstrap",
                )
                session.add(principal)
                await session.flush()
                if user.role != UserRole.ADMIN.value:
                    user.role = UserRole.ADMIN.value
                await self._security_event(
                    session,
                    SecurityEventType.ADMIN_CREATED,
                    principal=principal,
                    user=user,
                    severity="critical",
                    safe_error_code="config_bootstrap",
                )
                self._audit(
                    session,
                    actor_id=user.id,
                    action="admin.created",
                    entity_id=principal.id,
                    old_value=None,
                    new_value={"role": principal.role, "status": principal.status},
                )
            elif principal.status == AdminPrincipalStatus.ACTIVE.value:
                # A valid bootstrap owner may repair only the legacy role mirror;
                # it never resurrects a revoked/suspended principal.
                if (
                    principal.role != AdminRole.OWNER.value
                    and principal.bootstrap_source == "config_bootstrap"
                ):
                    principal.role = AdminRole.OWNER.value
                user.role = UserRole.ADMIN.value
            permissions = await self._permissions(session, principal)
            return self._principal(principal, user, permissions)

    async def resolve_principal(self, telegram_id: int) -> AdminPrincipal | None:
        """Resolve current DB state; legacy admin rows migrate once on demand."""
        async with self.db.session() as session:
            result = await session.execute(
                select(AdminPrincipalORM, UserORM)
                .join(UserORM, UserORM.id == AdminPrincipalORM.user_id)
                .where(UserORM.telegram_id == telegram_id)
            )
            pair = result.one_or_none()
            if pair is None:
                user = (
                    await session.execute(select(UserORM).where(UserORM.telegram_id == telegram_id))
                ).scalar_one_or_none()
                if user is None or user.role != UserRole.ADMIN.value:
                    return None
                principal = AdminPrincipalORM(
                    public_id=f"apr_{uuid4().hex[:24]}",
                    user_id=user.id,
                    status=AdminPrincipalStatus.ACTIVE.value,
                    role=AdminRole.ADMIN.value,
                    created_by=telegram_id,
                    bootstrap_source="legacy_role_migration",
                )
                session.add(principal)
                await session.flush()
                await self._security_event(
                    session,
                    SecurityEventType.ADMIN_CREATED,
                    principal=principal,
                    user=user,
                    severity="warning",
                    safe_error_code="legacy_role_migration",
                )
            else:
                principal, user = pair
            return self._principal(principal, user, await self._permissions(session, principal))

    async def authorize(
        self,
        telegram_id: int,
        permission: str | None = None,
        *,
        chat_type: str | None = None,
        critical: bool = False,
    ) -> Result[AdminPrincipal]:
        """Authorize using fresh DB state and deny unknown/missing data."""
        if permission is not None and permission not in _ALL_PERMISSION_KEYS:
            await self._record_security_failure(
                telegram_id, SecurityEventType.UNAUTHORIZED_ADMIN_ACCESS, "unknown_permission"
            )
            return self._failure("unknown_permission", "Action not permitted.")
        principal = await self.resolve_principal(telegram_id)
        if principal is None or principal.status != AdminPrincipalStatus.ACTIVE.value:
            await self._record_security_failure(
                telegram_id,
                SecurityEventType.UNAUTHORIZED_ADMIN_ACCESS,
                "inactive_or_unknown_admin",
            )
            return self._failure("admin_access_denied", "Action not permitted.")
        if critical and not self._chat_allowed(chat_type):
            await self._record_security_failure(
                telegram_id, SecurityEventType.UNAUTHORIZED_ADMIN_ACCESS, "critical_chat_policy"
            )
            return self._failure("chat_policy_denied", "Action not permitted.")
        if permission is not None and permission not in principal.permissions:
            await self._record_security_failure(
                telegram_id, SecurityEventType.UNAUTHORIZED_ADMIN_ACCESS, "permission_denied"
            )
            return self._failure("permission_denied", "Action not permitted.")
        return Result(value=principal)

    def _chat_allowed(self, chat_type: str | None) -> bool:
        if self.chat_policy == "any_chat_with_permission":
            return True
        if self.chat_policy == "private_only":
            return chat_type == "private"
        if self.chat_policy == "approved_chats":
            context = request_ctx.get()
            return bool(context and context.chat_id in self.approved_chat_ids)
        return False

    async def has_permission_for_user(self, user_id: int, permission: str) -> bool:
        try:
            await self.require_permission_for_user(user_id, permission)
        except PermissionDeniedException:
            return False
        return True

    async def require_permission_for_user(
        self,
        user_id: int,
        permission: str,
        *,
        chat_type: str | None = None,
        critical: bool = False,
    ) -> AdminPrincipal:
        """Reauthorize a persisted application user at a privileged service boundary."""
        async with self.db.session() as session:
            user = await session.get(UserORM, user_id)
        if user is None:
            raise PermissionDeniedException(message="Action not permitted.")
        return await self.require_permission(
            user.telegram_id,
            permission,
            chat_type=chat_type,
            critical=critical,
        )

    async def require_admin(self, telegram_id: int) -> AdminPrincipal:
        result = await self.authorize(telegram_id)
        if result.error is not None:
            raise PermissionDeniedException(message="Action not permitted.")
        return result.unwrap()

    async def require_permission(
        self,
        telegram_id: int,
        permission: str,
        *,
        chat_type: str | None = None,
        critical: bool = False,
    ) -> AdminPrincipal:
        result = await self.authorize(
            telegram_id, permission, chat_type=chat_type, critical=critical
        )
        if result.error is not None:
            raise PermissionDeniedException(message="Action not permitted.")
        return result.unwrap()

    async def create_challenge(
        self,
        telegram_id: int,
        *,
        action_type: str,
        permission: str,
        target_type: str | None = None,
        target_safe_id: str | None = None,
        payload: dict[str, Any] | None = None,
        chat_type: str | None = None,
    ) -> Result[ConfirmationChallenge]:
        if action_type not in CRITICAL_ACTIONS:
            return self._failure(
                "challenge_not_required", "This action does not require confirmation."
            )
        try:
            principal = await self.require_permission(
                telegram_id,
                permission,
                chat_type=chat_type,
                critical=True,
            )
        except PermissionDeniedException:
            return self._failure("permission_denied", "Action not permitted.")
        now = datetime.now(UTC)
        challenge = PrivilegedActionChallengeORM(
            public_id=f"pac_{uuid4().hex[:24]}",
            principal_id=principal.id,
            actor_telegram_id=telegram_id,
            action_type=action_type,
            target_type=target_type,
            target_safe_id=target_safe_id,
            payload_digest=self._digest(payload),
            expires_at=now + timedelta(seconds=self.confirmation_ttl_seconds),
        )
        async with self.db.session() as session:
            session.add(challenge)
            await session.flush()
            await self._security_event(
                session,
                SecurityEventType.CRITICAL_ACTION_CONFIRMED,
                principal_id=principal.id,
                actor_user_id=principal.user_id,
                target_type=target_type,
                target_safe_id=target_safe_id,
                severity="warning",
                safe_error_code="challenge_created",
            )
        return Result(
            value=ConfirmationChallenge(
                public_id=challenge.public_id,
                action_type=challenge.action_type,
                target_type=challenge.target_type,
                target_safe_id=challenge.target_safe_id,
                expires_at=challenge.expires_at,
            )
        )

    async def consume_challenge(  # noqa: PLR0911
        self,
        telegram_id: int,
        *,
        public_id: str,
        action_type: str,
        permission: str,
        target_type: str | None = None,
        target_safe_id: str | None = None,
        payload: dict[str, Any] | None = None,
        chat_type: str | None = None,
    ) -> Result[ConfirmationChallenge]:
        """Atomically consume a challenge only after full fresh revalidation."""
        try:
            principal = await self.require_permission(
                telegram_id, permission, chat_type=chat_type, critical=True
            )
        except PermissionDeniedException:
            return self._failure("permission_denied", "Action not permitted.")
        now = datetime.now(UTC)
        async with self.db.session() as session:
            challenge = (
                await session.execute(
                    select(PrivilegedActionChallengeORM)
                    .where(PrivilegedActionChallengeORM.public_id == public_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if challenge is None:
                return self._failure("challenge_not_found", "Confirmation is invalid.")
            if (
                challenge.principal_id != principal.id
                or challenge.actor_telegram_id != telegram_id
                or challenge.action_type != action_type
                or challenge.target_type != target_type
                or challenge.target_safe_id != target_safe_id
                or challenge.payload_digest != self._digest(payload)
            ):
                await self._security_event(
                    session,
                    SecurityEventType.FORGED_ADMIN_CALLBACK,
                    principal_id=principal.id,
                    actor_user_id=principal.user_id,
                    target_type=target_type,
                    target_safe_id=target_safe_id,
                    severity="warning",
                    safe_error_code="challenge_binding_mismatch",
                )
                return self._failure("challenge_binding_mismatch", "Confirmation is invalid.")
            if challenge.used_at is not None or challenge.invalidated_at is not None:
                return self._failure("challenge_used", "Confirmation is no longer valid.")
            expires_at = challenge.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= now:
                return self._failure("challenge_expired", "Confirmation has expired.")
            challenge.used_at = now
            principal_row = await session.get(AdminPrincipalORM, principal.id, with_for_update=True)
            if principal_row is None or principal_row.status != AdminPrincipalStatus.ACTIVE.value:
                return self._failure("admin_access_denied", "Action not permitted.")
            principal_row.last_privileged_at = now
            self._audit(
                session,
                actor_id=principal.user_id,
                action="critical_action.executed",
                entity_id=principal.id,
                old_value={"challenge": challenge.public_id},
                new_value={"action": challenge.action_type, "target": challenge.target_safe_id},
            )
            await self._security_event(
                session,
                SecurityEventType.CRITICAL_ACTION_EXECUTED,
                principal_id=principal.id,
                actor_user_id=principal.user_id,
                target_type=target_type,
                target_safe_id=target_safe_id,
                severity="warning",
                safe_error_code="challenge_consumed",
            )
            return Result(
                value=ConfirmationChallenge(
                    public_id=challenge.public_id,
                    action_type=challenge.action_type,
                    target_type=challenge.target_type,
                    target_safe_id=challenge.target_safe_id,
                    expires_at=challenge.expires_at,
                )
            )

    async def change_role(
        self,
        actor_telegram_id: int,
        target_telegram_id: int,
        new_role: str,
        *,
        reason: str | None = None,
    ) -> Result[AdminPrincipal]:
        if new_role not in ROLE_RANK:
            return self._failure("unknown_role", "Action not permitted.")
        try:
            actor = await self.require_permission(actor_telegram_id, "manage_admins")
        except PermissionDeniedException:
            return self._failure("permission_denied", "Action not permitted.")
        if actor_telegram_id == target_telegram_id or ROLE_RANK[new_role] >= ROLE_RANK.get(
            actor.role, -1
        ):
            await self._record_security_failure(
                actor_telegram_id,
                SecurityEventType.PRIVILEGE_ESCALATION_ATTEMPT,
                "role_scope_denied",
            )
            return self._failure("role_scope_denied", "Action not permitted.")
        async with self.db.session() as session:
            target = await self._load_principal(session, target_telegram_id)
            if target is None:
                return self._failure("admin_not_found", "Administrator not found.")
            principal, user = target
            if (
                principal.role == AdminRole.OWNER.value
                and new_role != AdminRole.OWNER.value
                and await self._active_owner_count(session) <= 1
            ):
                return self._failure(
                    "last_owner_protected", "At least one active owner is required."
                )
            old_role = principal.role
            principal.role = new_role
            self._audit(
                session,
                actor_id=actor.user_id,
                action="admin.role_changed",
                entity_id=principal.id,
                old_value={"role": old_role},
                new_value={"role": new_role},
            )
            principal.session_version += 1
            await self._invalidate_challenges(session, principal.id, "role_changed")
            await self._security_event(
                session,
                SecurityEventType.ADMIN_ROLE_CHANGED,
                principal=principal,
                user=user,
                target_type="admin_principal",
                target_safe_id=principal.public_id,
                severity="warning",
                metadata={
                    "old_role": old_role,
                    "new_role": new_role,
                    "reason": (reason or "")[:500],
                },
            )
            permissions = await self._permissions(session, principal)
            return Result(value=self._principal(principal, user, permissions))

    async def change_status(
        self,
        actor_telegram_id: int,
        target_telegram_id: int,
        status: str,
        *,
        reason: str | None = None,
    ) -> Result[AdminPrincipal]:
        if status not in {item.value for item in AdminPrincipalStatus}:
            return self._failure("unknown_admin_status", "Action not permitted.")
        try:
            await self.require_permission(actor_telegram_id, "manage_admins")
        except PermissionDeniedException:
            return self._failure("permission_denied", "Action not permitted.")
        async with self.db.session() as session:
            target = await self._load_principal(session, target_telegram_id)
            if target is None:
                return self._failure("admin_not_found", "Administrator not found.")
            principal, user = target
            if (
                principal.role == AdminRole.OWNER.value
                and status != AdminPrincipalStatus.ACTIVE.value
                and await self._active_owner_count(session) <= 1
            ):
                return self._failure(
                    "last_owner_protected", "At least one active owner is required."
                )
            if (
                actor_telegram_id == target_telegram_id
                and status != AdminPrincipalStatus.ACTIVE.value
            ):
                return self._failure("self_lockout_denied", "Action not permitted.")
            old_status = principal.status
            principal.status = status
            self._audit(
                session,
                actor_id=actor_telegram_id,
                action=f"admin.{status}",
                entity_id=principal.id,
                old_value={"status": old_status},
                new_value={"status": status},
            )
            principal.session_version += 1
            if status == AdminPrincipalStatus.REVOKED.value:
                principal.revoked_at = datetime.now(UTC)
                principal.revoked_by = actor_telegram_id
            await self._invalidate_challenges(session, principal.id, f"status_{status}")
            event_type = {
                AdminPrincipalStatus.SUSPENDED.value: SecurityEventType.ADMIN_SUSPENDED,
                AdminPrincipalStatus.REVOKED.value: SecurityEventType.ADMIN_REVOKED,
                AdminPrincipalStatus.LOCKED.value: SecurityEventType.ADMIN_LOCKED,
            }.get(status, SecurityEventType.ADMIN_ROLE_CHANGED)
            await self._security_event(
                session,
                event_type,
                principal=principal,
                user=user,
                target_type="admin_principal",
                target_safe_id=principal.public_id,
                severity="critical" if status != AdminPrincipalStatus.ACTIVE.value else "warning",
                metadata={
                    "old_status": old_status,
                    "new_status": status,
                    "reason": (reason or "")[:500],
                },
            )
            permissions = await self._permissions(session, principal)
            return Result(value=self._principal(principal, user, permissions))

    async def grant_permission(
        self,
        actor_telegram_id: int,
        target_telegram_id: int,
        permission: str,
        *,
        granted: bool = True,
        reason: str | None = None,
    ) -> Result[AdminPrincipal]:
        if permission not in _ALL_PERMISSION_KEYS:
            return self._failure("unknown_permission", "Action not permitted.")
        try:
            await self.require_permission(actor_telegram_id, "manage_permissions")
        except PermissionDeniedException:
            return self._failure("permission_denied", "Action not permitted.")
        if actor_telegram_id == target_telegram_id:
            return self._failure("self_escalation_denied", "Action not permitted.")
        async with self.db.session() as session:
            target = await self._load_principal(session, target_telegram_id)
            if target is None:
                return self._failure("admin_not_found", "Administrator not found.")
            principal, user = target
            grant = (
                await session.execute(
                    select(AdminPermissionGrantORM)
                    .where(
                        AdminPermissionGrantORM.principal_id == principal.id,
                        AdminPermissionGrantORM.permission == permission,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if grant is None:
                grant = AdminPermissionGrantORM(
                    principal_id=principal.id,
                    permission=permission,
                    granted=granted,
                    granted_by=actor_telegram_id,
                    reason=(reason or "")[:500],
                )
                session.add(grant)
            else:
                grant.granted = granted
                grant.granted_by = actor_telegram_id
                grant.reason = (reason or "")[:500]
            principal.session_version += 1
            self._audit(
                session,
                actor_id=actor_telegram_id,
                action="admin.permission_changed",
                entity_id=principal.id,
                old_value=None,
                new_value={"permission": permission, "granted": granted},
            )
            await self._invalidate_challenges(session, principal.id, "permission_changed")
            await self._security_event(
                session,
                SecurityEventType.ADMIN_PERMISSION_CHANGED,
                principal=principal,
                user=user,
                target_type="admin_principal",
                target_safe_id=principal.public_id,
                severity="critical",
                metadata={
                    "permission": permission,
                    "granted": granted,
                    "reason": (reason or "")[:500],
                },
            )
            return Result(
                value=self._principal(principal, user, await self._permissions(session, principal))
            )

    async def _load_principal(
        self, session: Any, telegram_id: int
    ) -> tuple[AdminPrincipalORM, UserORM] | None:
        result = await session.execute(
            select(AdminPrincipalORM, UserORM)
            .join(UserORM, UserORM.id == AdminPrincipalORM.user_id)
            .where(UserORM.telegram_id == telegram_id)
            .with_for_update()
        )
        return result.one_or_none()

    async def _permissions(self, session: Any, principal: AdminPrincipalORM) -> set[str]:
        permissions = set(ROLE_PERMISSION_POLICY.get(principal.role, frozenset()))
        if principal.role == AdminRole.ADMIN.value:
            from app.models.enums import ROLE_PERMISSIONS

            permissions.update(ROLE_PERMISSIONS.get(UserRole.ADMIN.value, []))
        grants = (
            await session.execute(
                select(AdminPermissionGrantORM).where(
                    AdminPermissionGrantORM.principal_id == principal.id
                )
            )
        ).scalars()
        for grant in grants:
            if grant.granted:
                permissions.add(grant.permission)
            else:
                permissions.discard(grant.permission)
        return permissions

    @staticmethod
    async def _active_owner_count(session: Any) -> int:
        return int(
            (
                await session.execute(
                    select(func.count(AdminPrincipalORM.id)).where(
                        AdminPrincipalORM.role == AdminRole.OWNER.value,
                        AdminPrincipalORM.status == AdminPrincipalStatus.ACTIVE.value,
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def _invalidate_challenges(session: Any, principal_id: int, reason: str) -> None:
        await session.execute(
            update(PrivilegedActionChallengeORM)
            .where(
                PrivilegedActionChallengeORM.principal_id == principal_id,
                PrivilegedActionChallengeORM.used_at.is_(None),
                PrivilegedActionChallengeORM.invalidated_at.is_(None),
            )
            .values(invalidated_at=datetime.now(UTC), invalidation_reason=reason)
        )

    async def _record_security_failure(
        self,
        telegram_id: int,
        event_type: SecurityEventType,
        safe_error_code: str,
    ) -> None:
        async with self.db.session() as session:
            pair = await self._load_principal(session, telegram_id)
            principal = pair[0] if pair else None
            user = (
                pair[1]
                if pair
                else (
                    await session.execute(select(UserORM).where(UserORM.telegram_id == telegram_id))
                ).scalar_one_or_none()
            )
            await self._security_event(
                session,
                event_type,
                principal=principal,
                user=user,
                severity="warning",
                safe_error_code=safe_error_code,
            )

    @staticmethod
    def _audit(
        session: Any,
        *,
        actor_id: int | None,
        action: str,
        entity_id: int | None,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
    ) -> None:
        session.add(
            AuditLogORM(
                actor_id=actor_id,
                action=action,
                entity_type="AdminPrincipal",
                entity_id=entity_id,
                old_value=json.dumps(old_value or {}, sort_keys=True),
                new_value=json.dumps(new_value or {}, sort_keys=True),
                note="Phase 8.1 admin security mutation",
            )
        )

    @staticmethod
    async def _security_event(
        session: Any,
        event_type: SecurityEventType,
        *,
        principal: AdminPrincipalORM | None = None,
        user: UserORM | None = None,
        principal_id: int | None = None,
        actor_user_id: int | None = None,
        target_type: str | None = None,
        target_safe_id: str | None = None,
        severity: str = "warning",
        safe_error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ctx = request_ctx.get()
        event = SecurityEventORM(
            event_type=event_type.value,
            severity=severity,
            actor_user_id=actor_user_id if actor_user_id is not None else getattr(user, "id", None),
            actor_principal_id=principal_id
            if principal_id is not None
            else getattr(principal, "id", None),
            target_type=target_type,
            target_safe_id=target_safe_id,
            request_id=get_request_id() or None,
            correlation_id=getattr(ctx, "correlation_id", None),
            safe_error_code=safe_error_code,
            metadata_json=json.dumps(metadata or {}, sort_keys=True, separators=(",", ":")),
        )
        session.add(event)
        await bus.emit(
            EventType.SECURITY_EVENT_RECORDED,
            security_event_type=event_type.value,
            severity=severity,
            safe_error_code=safe_error_code,
            target_type=target_type,
            target_safe_id=target_safe_id,
        )
