"""Centralized selective maintenance and incident policy."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.events import EventType, bus
from app.services.base import BaseService
from locales.translator import t
from database.models.audit_log import AuditLogORM
from database.models.maintenance import (
    AutoEndPolicy,
    CustomerImpact,
    IncidentSeverity,
    IncidentStatus,
    MaintenanceActionORM,
    MaintenanceReason,
    MaintenanceScope,
    MaintenanceState,
    MaintenanceWindowORM,
    MaintenanceWindowStatus,
    OperationalIncidentORM,
)


class MaintenanceBlockedError(RuntimeError):
    def __init__(self, scope: str, operation: str, state: str):
        self.scope = scope
        self.operation = operation
        self.state = state
        super().__init__(f"maintenance_blocked:{scope}:{operation}:{state}")


class MaintenanceService(BaseService):
    """Database-backed source of truth for maintenance and incident policy."""

    _STATE_STRENGTH = {
        MaintenanceState.NORMAL.value: 0,
        MaintenanceState.DEGRADED.value: 1,
        MaintenanceState.READ_ONLY.value: 2,
        MaintenanceState.MAINTENANCE.value: 3,
        MaintenanceState.EMERGENCY.value: 4,
    }
    _SAFE_OPERATIONS = {"VIEW", "READ", "SUPPORT", "HEALTH", "RECOVERY", "ADMIN_RECOVERY", "FINALIZE_EXISTING_PAYMENT"}
    _MUTATING_OPERATIONS = {"CREATE", "UPDATE", "DELETE", "REDEEM", "PROVISION", "PURCHASE", "CREDIT", "RETRY", "CLAIM", "SPEND", "WRITE"}
    _CONTROL_ACTION_LIMIT = 10
    _CONTROL_ACTION_WINDOW = timedelta(seconds=60)

    async def _record_control_action(self, session, *, actor_id: int, action: str, idempotency_key: str, window_id: int | None = None, metadata: dict | None = None):
        existing = (await session.execute(select(MaintenanceActionORM).where(MaintenanceActionORM.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing is not None:
            return existing, True
        cutoff = self._now() - self._CONTROL_ACTION_WINDOW
        recent = await session.scalar(select(func.count(MaintenanceActionORM.id)).where(MaintenanceActionORM.actor_id == actor_id, MaintenanceActionORM.created_at >= cutoff))
        if int(recent or 0) >= self._CONTROL_ACTION_LIMIT:
            raise RuntimeError("maintenance_rate_limited")
        safe_metadata = metadata or {}
        row = MaintenanceActionORM(idempotency_key=idempotency_key[:160], actor_id=actor_id, action=action[:64], window_id=window_id, result_code="accepted", metadata_json=json.dumps(safe_metadata, sort_keys=True))
        session.add(row)
        await session.flush()
        session.add(AuditLogORM(actor_id=actor_id, action=f"maintenance.{action}", entity_type="MaintenanceWindow", entity_id=window_id, old_value=None, new_value=json.dumps(safe_metadata, sort_keys=True), note="Operational maintenance control action"))
        return row, False

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _public(row: MaintenanceWindowORM) -> dict:
        return {
            "public_id": row.public_id,
            "scope": row.scope,
            "state": row.state,
            "status": row.status,
            "reason_code": row.reason_code,
            "customer_message_key": row.customer_message_key,
            "customer_message_text": row.customer_message_text,
            "starts_at": row.starts_at,
            "expected_ends_at": row.expected_ends_at,
            "ended_at": row.ended_at,
            "scheduled": row.scheduled,
            "alert_suppression_policy": row.alert_suppression_policy,
            "auto_end_policy": row.auto_end_policy,
            "incident_id": row.incident_id,
        }

    @staticmethod
    def _incident_public(row: OperationalIncidentORM) -> dict:
        return {
            "public_id": row.public_id,
            "title": row.title,
            "incident_type": row.incident_type,
            "severity": row.severity,
            "status": row.status,
            "started_at": row.started_at,
            "detected_at": row.detected_at,
            "acknowledged_at": row.acknowledged_at,
            "resolved_at": row.resolved_at,
            "owner_admin_id": row.owner_admin_id,
            "customer_impact": row.customer_impact,
            "safe_summary": row.safe_summary,
            "maintenance_window_id": row.maintenance_window_id,
        }

    async def get_effective_state(self, scope: str | MaintenanceScope, *, at: datetime | None = None) -> dict:
        now = at or self._now()
        scope_value = getattr(scope, "value", scope)
        scopes = [MaintenanceScope.GLOBAL.value, scope_value] if scope_value != MaintenanceScope.GLOBAL.value else [scope_value]
        async with self.db.session() as session:
            rows = (await session.execute(
                select(MaintenanceWindowORM).where(
                    MaintenanceWindowORM.scope.in_(scopes),
                    MaintenanceWindowORM.status == MaintenanceWindowStatus.ACTIVE.value,
                    MaintenanceWindowORM.starts_at <= now,
                ).order_by(MaintenanceWindowORM.starts_at.desc())
            )).scalars().all()
        if not rows:
            return {"scope": scope_value, "state": MaintenanceState.NORMAL.value, "source": None, "window": None}
        winner = max(rows, key=lambda row: self._STATE_STRENGTH.get(row.state, 0))
        return {"scope": scope_value, "state": winner.state, "source": winner.scope, "window": self._public(winner)}

    async def is_operation_allowed(self, scope: str | MaintenanceScope, operation: str, *, actor: dict | None = None) -> bool:
        state = (await self.get_effective_state(scope))["state"]
        op = operation.upper()
        actor = actor or {}
        if actor.get("maintenance_bypass") is True and actor.get("is_admin") is True:
            return True
        if state == MaintenanceState.NORMAL.value:
            return True
        if op in self._SAFE_OPERATIONS:
            return True
        if state == MaintenanceState.DEGRADED.value and op not in self._MUTATING_OPERATIONS:
            return True
        return False

    async def assert_operation_allowed(self, scope: str | MaintenanceScope, operation: str, *, actor: dict | None = None) -> None:
        result = await self.is_operation_allowed(scope, operation, actor=actor)
        if not result:
            effective = await self.get_effective_state(scope)
            raise MaintenanceBlockedError(getattr(scope, "value", scope), operation, effective["state"])

    async def schedule_maintenance(
        self,
        *,
        scope: str | MaintenanceScope,
        state: str | MaintenanceState = MaintenanceState.MAINTENANCE,
        starts_at: datetime | None = None,
        expected_ends_at: datetime | None = None,
        reason_code: str | MaintenanceReason = MaintenanceReason.OPERATOR_ACTION,
        created_by: int,
        customer_message_key: str | None = "customer.maintenance.default",
        customer_message_text: str | None = None,
        alert_suppression_policy: str = "scoped",
        auto_end_policy: str | AutoEndPolicy = AutoEndPolicy.REQUIRE_ADMIN_APPROVAL,
        idempotency_key: str | None = None,
    ) -> dict:
        start = starts_at or self._now()
        scope_value = getattr(scope, "value", scope)
        state_value = getattr(state, "value", state)
        reason_value = getattr(reason_code, "value", reason_code)
        auto_end_value = getattr(auto_end_policy, "value", auto_end_policy)
        if scope_value not in {item.value for item in MaintenanceScope}:
            raise ValueError("unsupported maintenance scope")
        if state_value not in self._STATE_STRENGTH:
            raise ValueError("unsupported maintenance state")
        if expected_ends_at and expected_ends_at <= start:
            raise ValueError("expected end must be after start")
        now = self._now()
        status = MaintenanceWindowStatus.ACTIVE.value if start <= now else MaintenanceWindowStatus.SCHEDULED.value
        async with self.db.session() as session:
            await self._record_control_action(session, actor_id=created_by, action="schedule", idempotency_key=idempotency_key or f"maintenance:schedule:{created_by}:{scope_value}:{start.isoformat()}:{state_value}", metadata={"scope": scope_value, "state": state_value, "reason_code": reason_value})
            if status == MaintenanceWindowStatus.ACTIVE.value:
                existing = (await session.execute(select(MaintenanceWindowORM).where(MaintenanceWindowORM.scope == scope_value, MaintenanceWindowORM.status == MaintenanceWindowStatus.ACTIVE.value))).scalar_one_or_none()
                if existing:
                    return self._public(existing)
            row = MaintenanceWindowORM(public_id=f"mw_{uuid4().hex[:20]}", scope=scope_value, state=state_value, status=status, reason_code=reason_value, customer_message_key=customer_message_key, customer_message_text=customer_message_text, starts_at=start, expected_ends_at=expected_ends_at, created_by=created_by, scheduled=start > now, alert_suppression_policy=alert_suppression_policy, auto_end_policy=auto_end_value)
            session.add(row)
            await session.flush()
            result = self._public(row)
        await bus.emit(EventType.MAINTENANCE_STARTED if status == MaintenanceWindowStatus.ACTIVE.value else EventType.MAINTENANCE_SCHEDULED, public_id=result["public_id"], scope=scope_value, state=state_value, created_by=created_by)
        return result

    async def activate_due_windows(self, *, at: datetime | None = None) -> dict:
        now = at or self._now()
        activated = 0
        async with self.db.session() as session:
            rows = (await session.execute(select(MaintenanceWindowORM).where(MaintenanceWindowORM.status == MaintenanceWindowStatus.SCHEDULED.value, MaintenanceWindowORM.starts_at <= now))).scalars().all()
            for row in rows:
                active = (await session.execute(select(MaintenanceWindowORM).where(MaintenanceWindowORM.scope == row.scope, MaintenanceWindowORM.status == MaintenanceWindowStatus.ACTIVE.value))).scalar_one_or_none()
                if active:
                    row.status = MaintenanceWindowStatus.CANCELLED.value
                    continue
                row.status = MaintenanceWindowStatus.ACTIVE.value
                activated += 1
        if activated:
            await bus.emit(EventType.MAINTENANCE_STARTED, count=activated)
        return {"activated": activated}

    async def end_maintenance(self, public_id: str, *, ended_by: int, force: bool = False, recovery_ok: bool = True, bypass_authorized: bool = False, idempotency_key: str | None = None) -> dict:
        if force and not bypass_authorized:
            return {"ended": False, "safe_error_code": "bypass_not_authorized"}
        async with self.db.session() as session:
            row = (await session.execute(select(MaintenanceWindowORM).where(MaintenanceWindowORM.public_id == public_id).with_for_update())).scalar_one_or_none()
            if row is None:
                return {"ended": False, "safe_error_code": "maintenance_not_found"}
            if row.status != MaintenanceWindowStatus.ACTIVE.value:
                return {"ended": False, "safe_error_code": "maintenance_not_active"}
            await self._record_control_action(session, actor_id=ended_by, action="end", idempotency_key=idempotency_key or f"maintenance:end:{ended_by}:{public_id}", window_id=row.id, metadata={"public_id": public_id, "force": force})
            if not recovery_ok and not force:
                await bus.emit(EventType.MAINTENANCE_RECOVERY_FAILED, public_id=public_id, scope=row.scope)
                return {"ended": False, "safe_error_code": "recovery_check_failed", "status": row.status}
            row.status = MaintenanceWindowStatus.COMPLETED.value
            row.ended_at = self._now()
            row.ended_by = ended_by
            result = self._public(row)
        await bus.emit(EventType.MAINTENANCE_ENDED, public_id=public_id, scope=result["scope"], force=force, ended_by=ended_by)
        return {"ended": True, "window": result}

    async def cancel_scheduled_maintenance(self, public_id: str, *, cancelled_by: int, idempotency_key: str | None = None) -> dict:
        async with self.db.session() as session:
            row = (await session.execute(select(MaintenanceWindowORM).where(MaintenanceWindowORM.public_id == public_id).with_for_update())).scalar_one_or_none()
            if row is None or row.status != MaintenanceWindowStatus.SCHEDULED.value:
                return {"cancelled": False, "safe_error_code": "scheduled_window_not_found"}
            await self._record_control_action(session, actor_id=cancelled_by, action="cancel", idempotency_key=idempotency_key or f"maintenance:cancel:{cancelled_by}:{public_id}", window_id=row.id, metadata={"public_id": public_id})
            row.status = MaintenanceWindowStatus.CANCELLED.value
        await bus.emit(EventType.MAINTENANCE_CANCELLED, public_id=public_id, cancelled_by=cancelled_by)
        return {"cancelled": True, "public_id": public_id}

    async def list_windows(self, *, active_only: bool = False, limit: int = 50) -> list[dict]:
        async with self.db.session() as session:
            query = select(MaintenanceWindowORM).order_by(MaintenanceWindowORM.starts_at.desc()).limit(min(max(limit, 1), 100))
            if active_only:
                query = query.where(MaintenanceWindowORM.status == MaintenanceWindowStatus.ACTIVE.value)
            rows = (await session.execute(query)).scalars().all()
        return [self._public(row) for row in rows]

    async def create_incident(self, *, title: str, incident_type: str, severity: str, created_by: int, safe_summary: str, customer_impact: str = CustomerImpact.NONE.value) -> dict:
        if len(title) > 160 or len(safe_summary) > 600:
            raise ValueError("incident text exceeds safe length")
        async with self.db.session() as session:
            row = OperationalIncidentORM(public_id=f"inc_{uuid4().hex[:20]}", title=title.strip(), incident_type=incident_type[:48], severity=severity, status=IncidentStatus.OPEN.value, started_at=self._now(), detected_at=self._now(), customer_impact=customer_impact, safe_summary=safe_summary.strip())
            session.add(row)
            await session.flush()
            result = self._incident_public(row)
        await bus.emit(EventType.INCIDENT_CREATED, public_id=result["public_id"], severity=severity, incident_type=incident_type, created_by=created_by)
        return result

    async def list_incidents(self, *, active_only: bool = True, limit: int = 50) -> list[dict]:
        async with self.db.session() as session:
            query = select(OperationalIncidentORM).order_by(OperationalIncidentORM.started_at.desc()).limit(min(max(limit, 1), 100))
            if active_only:
                query = query.where(OperationalIncidentORM.status.not_in([IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value]))
            rows = (await session.execute(query)).scalars().all()
        return [self._incident_public(row) for row in rows]

    async def is_alert_suppressed(self, scope: str | MaintenanceScope, alert_key: str, *, at: datetime | None = None) -> dict:
        effective = await self.get_effective_state(scope, at=at)
        window = effective.get("window")
        policy = (window or {}).get("alert_suppression_policy")
        suppressed = bool(window and policy in {"scoped", "global", "all"})
        if policy == "none":
            suppressed = False
        if policy == "global" and (window or {}).get("scope") != MaintenanceScope.GLOBAL.value:
            suppressed = False
        return {"suppressed": suppressed, "alert_key": alert_key, "scope": getattr(scope, "value", scope), "window": window, "reason": "planned_maintenance" if suppressed else None}

    async def recovery_check(self, scope: str | MaintenanceScope) -> dict:
        effective = await self.get_effective_state(scope)
        return {"scope": getattr(scope, "value", scope), "healthy": effective["state"] in {MaintenanceState.NORMAL.value, MaintenanceState.DEGRADED.value}, "state": effective["state"], "safe_error_code": None}

    async def process_due_windows(self, *, at: datetime | None = None) -> dict:
        """Activate due windows and safely process expected end times.

        Windows requiring approval are never ended automatically; they remain
        active and are surfaced to the admin control plane for an explicit,
        recovery-checked exit.
        """
        activation = await self.activate_due_windows(at=at)
        now = at or self._now()
        auto_ended = 0
        reminders = 0
        async with self.db.session() as session:
            rows = (await session.execute(select(MaintenanceWindowORM).where(MaintenanceWindowORM.status == MaintenanceWindowStatus.ACTIVE.value, MaintenanceWindowORM.expected_ends_at.is_not(None), MaintenanceWindowORM.expected_ends_at <= now))).scalars().all()
            for row in rows:
                if row.auto_end_policy == AutoEndPolicy.AUTO_END.value:
                    row.status = MaintenanceWindowStatus.COMPLETED.value
                    row.ended_at = now
                    auto_ended += 1
                else:
                    row.status = MaintenanceWindowStatus.ENDING.value
                    reminders += 1
        if auto_ended:
            await bus.emit(EventType.MAINTENANCE_ENDED, count=auto_ended, automatic=True)
        return {"activated": activation["activated"], "auto_ended": auto_ended, "awaiting_recovery_approval": reminders}

    async def maintenance_recovery_snapshot(self) -> dict:
        """Return a safe operational snapshot used by the recovery-check job."""
        async with self.db.session() as session:
            rows = (await session.execute(select(MaintenanceWindowORM).where(MaintenanceWindowORM.status.in_([MaintenanceWindowStatus.ACTIVE.value, MaintenanceWindowStatus.ENDING.value])))).scalars().all()
        checks = [await self.recovery_check(row.scope) for row in rows]
        return {"active_windows": len(rows), "checks": checks, "healthy": all(item["healthy"] for item in checks)}

    async def get_customer_notice(self, scope: str | MaintenanceScope, *, language: str = "en") -> str | None:
        effective = await self.get_effective_state(scope)
        window = effective.get("window")
        if not window:
            return None
        if window.get("customer_message_text"):
            return str(window["customer_message_text"])
        return t(window.get("customer_message_key") or "customer.maintenance.default", language=language)
