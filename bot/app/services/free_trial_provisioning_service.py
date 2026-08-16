from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.result import Failure, Success
from app.events import EventType, bus
from app.models.vpn_provisioning import ProvisioningSource, VPNProvisioningRequest
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.server import ServerORM
from database.models.server_reservation import ServerCapacityReservationORM


class FreeTrialProvisioningService:
    """Provision one accepted Free Trial claim through the Phase 4 saga.

    The service never creates a remote key directly. It consumes the pending
    Phase 5.4 reservation, pins the Phase 4 selection request to that server,
    applies the claim snapshot policy, and only then commits the reservation
    and binds the resulting local VPN key to the claim.
    """

    def __init__(
        self,
        db,
        provisioning_service,
        lifecycle_service=None,
        data_limit_service=None,
    ) -> None:
        self.db = db
        self.provisioning = provisioning_service
        self.lifecycle = lifecycle_service
        self.data_limit = data_limit_service

    async def provision_claim(self, *, claim_id: int):
        if claim_id <= 0:
            return Failure("invalid_claim", "Free VPN claim id must be positive.")

        async with self.db.session() as session:
            claim = (
                await session.execute(
                    select(FreeTrialClaimORM)
                    .where(FreeTrialClaimORM.id == claim_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if claim is None:
                return Failure("claim_not_found", "Free VPN claim was not found.")

            if claim.vpn_key_id:
                return Success(claim.vpn_key_id)
            if claim.status not in {"server_reserved", "provisioning"}:
                return Failure(
                    "claim_not_provisionable",
                    "Free VPN claim is not reserved for provisioning.",
                )

            reservation = (
                await session.execute(
                    select(ServerCapacityReservationORM)
                    .where(
                        ServerCapacityReservationORM.claim_id == claim_id,
                        ServerCapacityReservationORM.status
                        == ServerCapacityReservationORM.STATUS_PENDING,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if reservation is None:
                return Failure(
                    "reservation_not_found",
                    "Free VPN server reservation was not found.",
                )

            server = await session.get(ServerORM, reservation.server_id)
            if server is None:
                return Failure("server_not_found", "Reserved Free Trial server was not found.")

            claim.status = "provisioning"
            user_id = int(claim.user_id)
            package_id = int(claim.package_id)
            server_public_id = server.public_server_id
            data_limit_bytes = int(claim.data_limit_bytes)
            duration_days = max(1, math.ceil(int(claim.duration_seconds) / 86400))
            device_limit = claim.device_limit
            idempotency_key = f"free-trial-claim:{claim_id}"

        request = VPNProvisioningRequest(
            user_id=user_id,
            source_type=ProvisioningSource.FREE_TRIAL,
            workload_type="free_trial",
            package_id=package_id,
            specific_server_id=server_public_id,
            requested_data_limit_bytes=data_limit_bytes,
            requested_duration_days=duration_days,
            requested_device_limit=device_limit,
            idempotency_key=idempotency_key,
            request_reference=idempotency_key,
            metadata={"claim_id": claim_id, "reservation_id": reservation.public_reservation_id},
            reserve_capacity=False,
            allow_fallback=False,
            max_server_attempts=1,
        )
        result = await self.provisioning.provision(request, actor_user_id=user_id)
        if getattr(result, "is_failure", False):
            await self._restore_claim_after_failure(claim_id)
            return result

        success = getattr(result, "value", result)
        vpn_key_id = int(getattr(success, "vpn_key_id", 0))
        operation_id = getattr(success, "operation_id", idempotency_key)
        if vpn_key_id <= 0:
            await self._restore_claim_after_failure(claim_id)
            return Failure("missing_vpn_key", "Free VPN provisioning did not return a local key.")

        if self.data_limit is not None:
            limit_result = await self.data_limit.apply_for_key(
                key_id=vpn_key_id,
                actor_user_id=user_id,
                requested_limit_bytes=data_limit_bytes,
                operation_id=operation_id,
            )
            if getattr(limit_result, "is_failure", False):
                return limit_result

        if self.lifecycle is not None:
            lifecycle_result = await self.lifecycle.activate_key(
                key_id=vpn_key_id,
                actor_user_id=user_id,
                duration_days=duration_days,
            )
            if getattr(lifecycle_result, "is_failure", False):
                return lifecycle_result

        return await self._finalize_claim(
            claim_id=claim_id,
            vpn_key_id=vpn_key_id,
            reservation_id=reservation.id,
        )

    async def _finalize_claim(self, *, claim_id: int, vpn_key_id: int, reservation_id: int):
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            claim = await session.get(FreeTrialClaimORM, claim_id, with_for_update=True)
            reservation = await session.get(
                ServerCapacityReservationORM, reservation_id, with_for_update=True
            )
            if claim is None or reservation is None:
                return Failure("finalize_failed", "Free VPN claim finalization records are missing.")
            if claim.vpn_key_id and claim.vpn_key_id != vpn_key_id:
                return Failure("claim_already_bound", "Free VPN claim is already bound to another key.")
            claim.vpn_key_id = vpn_key_id
            claim.status = "provisioned"
            reservation.status = ServerCapacityReservationORM.STATUS_COMMITTED
            reservation.committed_at = now
            user_id = int(claim.user_id)
        await bus.emit(EventType.FREE_TRIAL_ACTIVATED, user_id=user_id, claim_id=claim_id, vpn_key_id=vpn_key_id, source_reference=f"free_trial_claim:{claim_id}")
        return Success(vpn_key_id)

    async def _restore_claim_after_failure(self, claim_id: int) -> None:
        async with self.db.session() as session:
            claim = await session.get(FreeTrialClaimORM, claim_id, with_for_update=True)
            if claim is not None and claim.status == "provisioning":
                claim.status = "server_reserved"
