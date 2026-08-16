from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.core.result import Failure, Success
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.free_trial_entitlement import FreeTrialEntitlementORM
from database.models.package import PackageORM
from database.models.user import UserORM


class FreeTrialClaimService:
    """Phase 5.3 transactional acceptance boundary; it never creates a VPN key."""

    def __init__(self, db, settings_service=None):
        self.db = db
        self.settings_service = settings_service

    async def accept_claim(self, *, user_id: int, package_id: int | None, idempotency_key: str, policy: dict[str, object]):
        if user_id <= 0 or not idempotency_key:
            return Failure("invalid_claim", "Free Trial claim identity is invalid.")
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        async with self.db.session() as session:
            existing = (await session.execute(select(FreeTrialClaimORM).where(FreeTrialClaimORM.idempotency_key == idempotency_key).with_for_update())).scalar_one_or_none()
            if existing is not None:
                return Success(existing)
            user = (await session.execute(select(UserORM).where(UserORM.id == user_id).with_for_update())).scalar_one_or_none()
            if user is None or not user.is_active or user.status in {"banned", "suspended", "inactive"}:
                return Failure("account_inactive", "This account cannot claim Free VPN.")
            if not bool(policy.get("free_trial_enabled", False)):
                return Failure("free_trial_disabled", "Free VPN is temporarily unavailable.")
            package = None
            if package_id is not None:
                package = (await session.execute(select(PackageORM).where(PackageORM.id == package_id, PackageORM.package_type == "free_trial", PackageORM.is_active.is_(True), PackageORM.visible.is_(True), PackageORM.status == "active"))).scalar_one_or_none()
                if package is None:
                    return Failure("trial_unavailable", "Free VPN is not currently available.")
            period_source = "daily_free"
            normal_limit = int(policy.get("free_trial_normal_claims_per_period", 0) or 0)
            normal_used = await session.scalar(select(func.count(FreeTrialClaimORM.id)).where(FreeTrialClaimORM.user_id == user_id, FreeTrialClaimORM.period_start == period_start, FreeTrialClaimORM.source == period_source, FreeTrialClaimORM.status.not_in(("cancelled", "failed"))))
            source = period_source
            data_bytes = int(policy.get("free_trial_data_per_claim_bytes", 0) or 0)
            duration = int(policy.get("free_trial_duration_seconds", 0) or 0)
            device_limit = policy.get("free_trial_device_limit")
            entitlement = None
            if int(normal_used or 0) >= normal_limit:
                if not bool(policy.get("free_trial_extra_claims_enabled", False)):
                    return Failure("daily_allowance_exhausted", "Today’s Free VPN allowance has been used.")
                entitlement = (await session.execute(select(FreeTrialEntitlementORM).where(FreeTrialEntitlementORM.user_id == user_id, FreeTrialEntitlementORM.status == "active", FreeTrialEntitlementORM.remaining_uses > 0, (FreeTrialEntitlementORM.expires_at.is_(None) | (FreeTrialEntitlementORM.expires_at > now))).order_by(FreeTrialEntitlementORM.id).with_for_update())).scalars().first()
                if entitlement is None:
                    return Failure("no_extra_entitlement", "No extra Free VPN entitlement is available.")
                entitlement.remaining_uses -= 1
                source = "extra_entitlement"
                data_bytes = int(entitlement.data_limit_bytes or data_bytes)
                duration = int(entitlement.duration_seconds or duration)
                device_limit = entitlement.device_limit if entitlement.device_limit is not None else device_limit
            if data_bytes <= 0 or duration <= 0:
                return Failure("policy_invalid", "Free Trial data or duration policy is invalid.")
            claim = FreeTrialClaimORM(user_id=user_id, package_id=package_id or (package.id if package else 0), entitlement_id=entitlement.id if entitlement else None, idempotency_key=idempotency_key, period_start=period_start, source=source, status="accepted", data_limit_bytes=data_bytes, duration_seconds=duration, device_limit=int(device_limit) if device_limit is not None else None, policy_snapshot_json=json.dumps(dict(policy), sort_keys=True), claimed_at=now, accepted_at=now)
            session.add(claim)
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                replay = (await session.execute(select(FreeTrialClaimORM).where(FreeTrialClaimORM.user_id == user_id, FreeTrialClaimORM.period_start == period_start, FreeTrialClaimORM.source == "daily_free").order_by(FreeTrialClaimORM.id))).scalar_one_or_none()
                if replay is not None:
                    return Failure("daily_allowance_exhausted", "Today’s Free VPN allowance has been used.")
                return Failure("claim_conflict", "The Free VPN claim could not be accepted safely; please retry.")
            return Success(claim)

    async def cancel_claim(self, *, claim_id: int, reason: str):
        async with self.db.session() as session:
            claim = (await session.execute(select(FreeTrialClaimORM).where(FreeTrialClaimORM.id == claim_id).with_for_update())).scalar_one_or_none()
            if claim is None:
                return Failure("claim_not_found", "Free VPN claim was not found.")
            if claim.status in {"cancelled", "failed"}:
                return Success(claim)
            if claim.status in {"provisioning", "active"}:
                return Failure("claim_terminal", "This Free VPN claim cannot be cancelled now.")
            claim.status = "cancelled"
            claim.cancelled_at = datetime.now(timezone.utc)
            claim.cancellation_reason = (reason or "cancelled")[:96]
            if claim.entitlement_id:
                entitlement = await session.get(FreeTrialEntitlementORM, claim.entitlement_id, with_for_update=True)
                if entitlement is not None:
                    entitlement.remaining_uses += 1
            await session.flush()
            return Success(claim)
