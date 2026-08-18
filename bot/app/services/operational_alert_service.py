"""Concrete Phase 7.2 operational alert evaluator."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from app.events import EventType, bus
from database.models.maintenance import AlertSeverity, AlertStatus, OperationalAlertORM

if TYPE_CHECKING:
    from app.services.maintenance_service import MaintenanceService


class OperationalAlertService:
    ALERT_OUTLINE_UNREACHABLE = "OUTLINE_API_UNREACHABLE"

    def __init__(
        self,
        db: Any,
        *,
        maintenance_service: MaintenanceService | None = None,
        notification_service: Any = None,
    ) -> None:
        self.db = db
        self.maintenance = maintenance_service
        self.notifications = notification_service

    @staticmethod
    def fingerprint(alert_type: str, component: str) -> str:
        return sha256(f"{alert_type}:component:{component}".encode()).hexdigest()

    @staticmethod
    def _safe(row: OperationalAlertORM) -> dict[str, Any]:
        return {
            "id": row.id,
            "public_id": row.public_id,
            "fingerprint": row.fingerprint,
            "alert_type": row.alert_type,
            "component": row.component,
            "severity": row.severity,
            "status": row.status,
            "title": row.title,
            "safe_summary": row.safe_summary,
            "occurrence_count": row.occurrence_count,
            "incident_id": row.incident_id,
            "first_seen_at": row.first_seen_at,
            "last_seen_at": row.last_seen_at,
            "resolved_at": row.resolved_at,
        }

    async def evaluate_health_result(self, result: Any) -> dict[str, Any]:
        """Evaluate one authoritative HealthCheckResult from HealthService."""
        return await self.evaluate_component(
            component=result.component,
            healthy=result.status.value == "healthy",
            safe_summary=result.message_code
            or result.error_code
            or "Provider health check failed.",
            now=result.checked_at,
        )

    async def evaluate_component(  # noqa: PLR0912, PLR0915
        self,
        *,
        component: str,
        healthy: bool,
        safe_summary: str = "",
        now: datetime | None = None,
        create_incident: bool = True,
    ) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        alert_type = (
            self.ALERT_OUTLINE_UNREACHABLE
            if component in {"outline_apis", "vpn_servers"}
            else f"{component.upper()}_UNHEALTHY"
        )
        fingerprint = self.fingerprint(alert_type, component)
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(OperationalAlertORM)
                    .where(OperationalAlertORM.fingerprint == fingerprint)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if healthy:
                if row is None or row.status == AlertStatus.RESOLVED.value:
                    return {
                        "alert": self._safe(row) if row else None,
                        "opened": False,
                        "resolved": False,
                        "idempotent": True,
                    }
                row.status = AlertStatus.RESOLVED.value
                row.resolved_at = now
                row.last_seen_at = now
                row.recovery_metadata_json = json.dumps(
                    {"recovered_at": now.isoformat(), "source": "health_transition"}
                )
                result = self._safe(row)
                incident_id = row.incident_id
                should_notify_recovery = row.notification_state == "open_sent"
            else:
                if row is None:
                    row = OperationalAlertORM(
                        public_id=f"alrt_{uuid4().hex[:20]}",
                        fingerprint=fingerprint,
                        alert_type=alert_type,
                        component=component,
                        severity=AlertSeverity.CRITICAL.value
                        if component == "outline_apis"
                        else AlertSeverity.ERROR.value,
                        status=AlertStatus.OPEN.value,
                        title=f"{alert_type.replace('_', ' ').title()}",
                        safe_summary=safe_summary[:600],
                        first_seen_at=now,
                        last_seen_at=now,
                        occurrence_count=1,
                    )
                    session.add(row)
                    await session.flush()
                    opened = True
                else:
                    row.last_seen_at = now
                    row.occurrence_count = int(row.occurrence_count or 0) + 1
                    if row.status == AlertStatus.RESOLVED.value:
                        row.status = AlertStatus.OPEN.value
                        row.resolved_at = None
                    opened = False
                result = self._safe(row)
                incident_id = row.incident_id
                should_notify_open = opened or row.notification_state != "open_sent"
        if healthy:
            if incident_id and self.maintenance is not None:
                await self._resolve_incident_by_id(incident_id)
            delivery = None
            if self.notifications is not None and should_notify_recovery:
                delivery = await self.notifications.notify_admins(
                    f"Operational alert resolved: {result['title']}"
                )
                async with self.db.session() as session:
                    row = (
                        await session.execute(
                            select(OperationalAlertORM)
                            .where(OperationalAlertORM.public_id == result["public_id"])
                            .with_for_update()
                        )
                    ).scalar_one()
                    row.notification_attempts = int(row.notification_attempts or 0) + 1
                    row.notification_state = (
                        "resolved_sent"
                        if int(delivery.get("delivered", 0)) > 0
                        else "resolved_failed"
                    )
                    result = self._safe(row)
            await bus.emit(
                EventType.ALERT_RESOLVED,
                alert_public_id=result["public_id"],
                fingerprint=fingerprint,
                component=component,
            )
            return {
                "alert": result,
                "opened": False,
                "resolved": True,
                "idempotent": not should_notify_recovery,
                "notification": delivery,
            }
        maintenance_window = None
        if create_incident and incident_id is None and self.maintenance is not None:
            incident = await self.maintenance.create_incident(
                title=result["title"],
                incident_type=alert_type,
                severity=result["severity"],
                created_by=0,
                safe_summary=result["safe_summary"]
                or "Operational provider health is unavailable.",
            )
            async with self.db.session() as session:
                row = (
                    await session.execute(
                        select(OperationalAlertORM)
                        .where(OperationalAlertORM.public_id == result["public_id"])
                        .with_for_update()
                    )
                ).scalar_one()
                row.incident_id = incident.get("id")
                result = self._safe(row)
        if component == "outline_apis" and self.maintenance is not None:
            maintenance_window = await self.maintenance.schedule_maintenance(
                scope="vpn_provisioning",
                state="maintenance",
                reason_code="vpn_provider_outage",
                created_by=0,
                customer_message_key="customer.maintenance.vpn_provisioning",
                idempotency_key=f"alert-maintenance:{fingerprint}",
            )
        if self.notifications is not None and should_notify_open:
            delivery = await self.notifications.notify_admins(
                f"Operational alert: {result['title']}\n{result['safe_summary']}"
            )
        else:
            delivery = {
                "attempted": 0,
                "delivered": 0,
                "error_code": "notification_cycle_suppressed"
                if not should_notify_open
                else "notification_service_unavailable",
            }
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(OperationalAlertORM)
                    .where(OperationalAlertORM.public_id == result["public_id"])
                    .with_for_update()
                )
            ).scalar_one()
            if should_notify_open:
                row.notification_attempts = int(row.notification_attempts or 0) + 1
                row.notification_state = (
                    "open_sent" if int(delivery.get("delivered", 0)) > 0 else "open_failed"
                )
            result = self._safe(row)
        await bus.emit(
            EventType.ALERT_OPENED,
            alert_public_id=result["public_id"],
            fingerprint=fingerprint,
            component=component,
            alert_type=alert_type,
            deduplicated=not opened,
        )
        return {
            "alert": result,
            "opened": opened,
            "resolved": False,
            "idempotent": not opened,
            "maintenance_window": maintenance_window,
            "notification": delivery,
        }

    async def recover_component(
        self, *, component: str, now: datetime | None = None
    ) -> dict[str, Any]:
        result = await self.evaluate_component(component=component, healthy=True, now=now)
        maintenance = None
        if component == "outline_apis" and self.maintenance is not None:
            check = await self.maintenance.recovery_check(
                "vpn_provisioning", provider_healthy=True, queue_healthy=True
            )
            windows = await self.maintenance.list_windows(active_only=True)
            if check["healthy"] and windows:
                maintenance = await self.maintenance.end_maintenance(
                    windows[0]["public_id"],
                    ended_by=0,
                    recovery_ok=True,
                    idempotency_key=(
                        "alert-recovery:"
                        f"{self.fingerprint(self.ALERT_OUTLINE_UNREACHABLE, component)}"
                    ),
                )
            result["recovery_check"] = check
            result["maintenance_end"] = maintenance
        if self.notifications is not None and result.get("resolved"):
            result["notification"] = await self.notifications.notify_admins(
                f"Operational alert resolved: {result['alert']['title']}"
            )
        return result

    async def _resolve_incident_by_id(self, incident_id: int) -> None:
        if self.maintenance is None:
            return
        async with self.db.session() as session:
            from database.models.maintenance import OperationalIncidentORM

            row = await session.get(OperationalIncidentORM, incident_id)
            public_id = row.public_id if row else None
        if public_id:
            await self.maintenance.resolve_incident(public_id, resolved_by=0)

    async def list_open(self, limit: int = 100) -> list[dict]:
        async with self.db.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(OperationalAlertORM)
                        .where(
                            OperationalAlertORM.status.in_(
                                (
                                    AlertStatus.OPEN.value,
                                    AlertStatus.ACKNOWLEDGED.value,
                                    AlertStatus.SNOOZED.value,
                                )
                            )
                        )
                        .order_by(OperationalAlertORM.last_seen_at.desc())
                        .limit(min(max(limit, 1), 200))
                    )
                )
                .scalars()
                .all()
            )
        return [self._safe(row) for row in rows]
