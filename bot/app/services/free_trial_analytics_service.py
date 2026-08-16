from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.core.result import Failure, Success
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.free_trial_upgrade import FreeTrialRestrictionORM, FreeTrialUpgradeORM
from database.models.order import OrderORM
from database.models.server_reservation import ServerCapacityReservationORM
from database.models.vpn_key import VPNKeyORM


class FreeTrialAnalyticsService:
    """Read-only aggregate queries for the Phase 5.6 admin dashboard."""

    def __init__(self, db):
        self.db = db

    async def dashboard(self, *, actor_user_id: int, start: datetime | None = None, end: datetime | None = None):
        from database.models.user import UserORM
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_user_id)
            if actor is None or actor.role != "admin" or not actor.is_active:
                return Failure("permission_denied", "Admin permission required.")
            start = start or datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            end = end or datetime.now(timezone.utc)
            claim_filter = (FreeTrialClaimORM.created_at >= start, FreeTrialClaimORM.created_at < end)
            upgrade_filter = (FreeTrialUpgradeORM.created_at >= start, FreeTrialUpgradeORM.created_at < end)
            claims = {}
            for status in ("accepted", "server_reserved", "provisioning", "provisioned", "active", "cancelled", "failed"):
                claims[status] = int(await session.scalar(select(func.count(FreeTrialClaimORM.id)).where(FreeTrialClaimORM.status == status, *claim_filter)) or 0)
            upgrades = {}
            for status in ("payment_pending", "fulfillment_pending", "fulfilled", "failed"):
                upgrades[status] = int(await session.scalar(select(func.count(FreeTrialUpgradeORM.id)).where(FreeTrialUpgradeORM.status == status, *upgrade_filter)) or 0)
            revenue = await session.scalar(select(func.coalesce(func.sum(FreeTrialUpgradeORM.price_snapshot), 0)).where(FreeTrialUpgradeORM.status == "fulfilled", *upgrade_filter))
            restrictions = int(await session.scalar(select(func.count(FreeTrialRestrictionORM.id)).where(FreeTrialRestrictionORM.blocked.is_(True))) or 0)
            reservations = {}
            for status in ("pending", "committed", "released", "expired"):
                reservations[status] = int(await session.scalar(select(func.count(ServerCapacityReservationORM.id)).where(ServerCapacityReservationORM.workload_type == "free_trial", ServerCapacityReservationORM.status == status, *claim_filter)) or 0)
            conversions = int(await session.scalar(select(func.count(FreeTrialUpgradeORM.id)).where(FreeTrialUpgradeORM.upgrade_type == "PAID_PLAN_CONVERSION", FreeTrialUpgradeORM.status == "fulfilled", *upgrade_filter)) or 0)
            active_trials = int(await session.scalar(select(func.count(VPNKeyORM.id)).where(VPNKeyORM.key_type.in_(("free_trial", "free_trial_upgraded")), VPNKeyORM.status == "active")) or 0)
            return Success({"period": {"start": start, "end": end}, "claims": claims, "reservations": reservations, "upgrades": upgrades, "upgrade_revenue": Decimal(str(revenue or 0)), "paid_conversions": conversions, "active_trials": active_trials, "blocked_users": restrictions})
