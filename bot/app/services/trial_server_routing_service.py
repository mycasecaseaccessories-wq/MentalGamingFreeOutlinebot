from __future__ import annotations
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import secrets
from dataclasses import replace
from sqlalchemy import func, select
from app.core.result import Failure, Success
from app.models.server_selection import ServerSelectionRequest
from app.services.server_selection_service import ServerSelectionService
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.server import ServerORM
from database.models.server_reservation import ServerCapacityReservationORM
from database.repositories.server_repository import ServerRepository

class TrialServerRoutingService:
    """Routes an ACCEPTED claim to one quota-reserved server; never creates a key."""
    def __init__(self, db, *, selection_service: ServerSelectionService | None = None, reservation_ttl_seconds: int = 600, timezone_name: str = "Asia/Yangon"):
        self.db = db
        self.selection = selection_service or ServerSelectionService(db)
        self.reservation_ttl_seconds = reservation_ttl_seconds
        self.timezone_name = timezone_name

    def period_key(self, now: datetime | None = None) -> str:
        local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(self.timezone_name))
        return local.strftime("%Y-%m-%d")

    async def route_claim(self, *, claim_id: int, preferred_country: str | None = None):
        now = datetime.now(timezone.utc)
        period = self.period_key(now)
        async with self.db.session() as session:
            claim = (await session.execute(select(FreeTrialClaimORM).where(FreeTrialClaimORM.id == claim_id).with_for_update())).scalar_one_or_none()
            if claim is None:
                return Failure("claim_not_found", "Free VPN claim was not found.")
            existing = (await session.execute(select(ServerCapacityReservationORM).where(ServerCapacityReservationORM.claim_id == claim_id, ServerCapacityReservationORM.status.in_((ServerCapacityReservationORM.STATUS_PENDING, ServerCapacityReservationORM.STATUS_COMMITTED))).with_for_update())).scalar_one_or_none()
            if existing is not None:
                return Success(existing)
            if claim.status not in {"accepted", "queued"}:
                return Failure("claim_not_routeable", "Free VPN claim is not ready for server routing.")
            rows = await ServerRepository(session).list_for_selection()
            excluded: set[str] = set()
            request = ServerSelectionRequest(workload_type="free_trial", preferred_country=preferred_country, allow_fallback=True, exclude_server_ids=frozenset(), reservation_required=True, request_reference=f"free-trial-claim:{claim_id}")
            while True:
                request = replace(request, exclude_server_ids=frozenset(excluded))
                selection = self.selection.select_from_rows(rows, request)
                if selection.selected is None:
                    return Failure("no_trial_server", "No eligible Free Trial server is available right now.")
                selected_id = selection.selected.server_id
                excluded.add(selected_id)
                server = (await session.execute(select(ServerORM).where(ServerORM.public_server_id == selected_id).with_for_update())).scalar_one_or_none()
                if server is None:
                    continue
                if not server.free_trial_enabled or not server.enabled or not server.is_active or server.maintenance_mode:
                    continue
                if server.free_trial_daily_quota_enabled:
                    if server.free_trial_daily_quota is None or server.free_trial_daily_quota < 0:
                        return Failure("invalid_trial_quota", "Free Trial quota configuration is invalid.")
                    consumed = await session.scalar(select(func.count(ServerCapacityReservationORM.id)).where(ServerCapacityReservationORM.server_id == server.id, ServerCapacityReservationORM.workload_type == "free_trial", ServerCapacityReservationORM.period_key == period, ServerCapacityReservationORM.status.in_((ServerCapacityReservationORM.STATUS_PENDING, ServerCapacityReservationORM.STATUS_COMMITTED))))
                    if int(consumed or 0) >= server.free_trial_daily_quota:
                        continue
                active_capacity = await session.scalar(select(func.count(ServerCapacityReservationORM.id)).where(ServerCapacityReservationORM.server_id == server.id, ServerCapacityReservationORM.status == ServerCapacityReservationORM.STATUS_PENDING, ServerCapacityReservationORM.expires_at > now))
                if server.max_users is not None and server.current_users + int(active_capacity or 0) >= server.max_users:
                    continue
                row = ServerCapacityReservationORM(public_reservation_id="RSV-" + secrets.token_urlsafe(12), server_id=server.id, claim_id=claim_id, workload_type="free_trial", owner_reference=f"free-trial-claim:{claim_id}", period_key=period, status=ServerCapacityReservationORM.STATUS_PENDING, created_at=now, expires_at=now.replace(microsecond=0) + timedelta(seconds=self.reservation_ttl_seconds))
                session.add(row)
                claim.status = "server_reserved"
                await session.flush()
                return Success(row)

    async def release_reservation(self, *, claim_id: int, reason: str = "routing_failed"):
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            row = (await session.execute(select(ServerCapacityReservationORM).where(ServerCapacityReservationORM.claim_id == claim_id).with_for_update())).scalar_one_or_none()
            if row is None:
                return Failure("reservation_not_found", "Server reservation was not found.")
            if row.status in {ServerCapacityReservationORM.STATUS_RELEASED, ServerCapacityReservationORM.STATUS_EXPIRED}:
                return Success(row)
            if row.status == ServerCapacityReservationORM.STATUS_COMMITTED:
                return Failure("reservation_terminal", "Consumed server reservation cannot be released.")
            row.status = ServerCapacityReservationORM.STATUS_RELEASED
            row.released_at = now
            claim = await session.get(FreeTrialClaimORM, claim_id, with_for_update=True)
            if claim is not None and claim.status == "server_reserved":
                claim.status = "accepted"
            return Success(row)

    async def expire_reservations(self):
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            rows = list((await session.execute(select(ServerCapacityReservationORM).where(ServerCapacityReservationORM.workload_type == "free_trial", ServerCapacityReservationORM.status == ServerCapacityReservationORM.STATUS_PENDING, ServerCapacityReservationORM.expires_at <= now).with_for_update())).scalars().all())
            for row in rows:
                row.status = ServerCapacityReservationORM.STATUS_EXPIRED
                row.released_at = now
                claim = await session.get(FreeTrialClaimORM, row.claim_id, with_for_update=True) if row.claim_id else None
                if claim is not None and claim.status == "server_reserved":
                    claim.status = "accepted"
            return len(rows)
