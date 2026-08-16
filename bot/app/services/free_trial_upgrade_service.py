from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.core.result import Failure, Success
from app.events import EventType, bus
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.free_trial_upgrade import FreeTrialUpgradeOfferORM, FreeTrialUpgradeORM
from database.models.order import OrderORM
from database.models.package import PackageORM
from database.models.user import UserORM
from database.models.vpn_key import VPNKeyORM


DATA_ADDON = "DATA_ADDON"
DURATION_EXTENSION = "DURATION_EXTENSION"
DATA_AND_DURATION = "DATA_AND_DURATION"
PAID_PLAN_CONVERSION = "PAID_PLAN_CONVERSION"
_PAYMENT_PENDING = "payment_pending"
_FULFILLMENT_PENDING = "fulfillment_pending"
_FULFILLED = "fulfilled"


class FreeTrialUpgradeService:
    """Payment-to-benefit boundary for Free Trial upgrades and conversion."""

    def __init__(self, db, *, data_limit_service=None, lifecycle_service=None, settings_service=None, abuse_service=None):
        self.db = db
        self.data_limit = data_limit_service
        self.lifecycle = lifecycle_service
        self.settings = settings_service
        self.abuse = abuse_service

    async def get_available_offers(self, *, user_id: int, vpn_key_id: int):
        validation = await self.validate_target_vpn(user_id=user_id, vpn_key_id=vpn_key_id)
        if validation.is_failure:
            return validation
        async with self.db.session() as session:
            rows = (await session.execute(
                select(FreeTrialUpgradeOfferORM)
                .where(FreeTrialUpgradeOfferORM.enabled.is_(True), FreeTrialUpgradeOfferORM.archived_at.is_(None))
                .order_by(FreeTrialUpgradeOfferORM.sort_order.asc(), FreeTrialUpgradeOfferORM.id.asc())
            )).scalars().all()
            return Success(list(rows))

    async def validate_target_vpn(self, *, user_id: int, vpn_key_id: int):
        async with self.db.session() as session:
            key = (await session.execute(
                select(VPNKeyORM).where(VPNKeyORM.id == vpn_key_id).with_for_update()
            )).scalar_one_or_none()
            if key is None or key.user_id != user_id:
                return Failure("not_found", "VPN key was not found.")
            if key.key_type not in {"free_trial", "free_trial_upgraded"}:
                return Failure("not_trial_key", "Only a Free Trial VPN can be upgraded.")
            if not key.is_active or key.status not in {"active", "ready"}:
                return Failure("trial_not_active", "This Free Trial VPN is not active.")
            return Success(key)

    async def create_upgrade_order(self, *, user_id: int, vpn_key_id: int, offer_id: int, idempotency_key: str):
        if not idempotency_key or len(idempotency_key) > 96:
            return Failure("invalid_idempotency", "A valid upgrade request reference is required.")
        if self.settings is not None and not await self.settings.get("free_trial_paid_upgrade_enabled", True):
            return Failure("upgrade_disabled", "Paid Free Trial upgrades are temporarily unavailable.")
        if self.abuse is not None:
            risk = await self.abuse.evaluate_upgrade(user_id=user_id, vpn_key_id=vpn_key_id)
            if risk.is_failure:
                return risk
        async with self.db.session() as session:
            existing = (await session.execute(
                select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.idempotency_key == idempotency_key)
            )).scalar_one_or_none()
            if existing is not None:
                return Success(await self._order_summary(session, existing.order_id))
            key = (await session.execute(select(VPNKeyORM).where(VPNKeyORM.id == vpn_key_id).with_for_update())).scalar_one_or_none()
            if key is None or key.user_id != user_id:
                return Failure("not_found", "VPN key was not found.")
            if key.key_type not in {"free_trial", "free_trial_upgraded"} or not key.is_active:
                return Failure("trial_not_active", "This Free Trial VPN is not eligible for upgrade.")
            offer = (await session.execute(
                select(FreeTrialUpgradeOfferORM).where(
                    FreeTrialUpgradeOfferORM.id == offer_id,
                    FreeTrialUpgradeOfferORM.enabled.is_(True),
                    FreeTrialUpgradeOfferORM.archived_at.is_(None),
                ).with_for_update()
            )).scalar_one_or_none()
            if offer is None:
                return Failure("offer_not_found", "This upgrade offer is no longer available.")
            if offer.upgrade_type not in {DATA_ADDON, DURATION_EXTENSION, DATA_AND_DURATION, PAID_PLAN_CONVERSION}:
                return Failure("invalid_offer", "This upgrade offer type is not supported.")
            if offer.upgrade_type == PAID_PLAN_CONVERSION and offer.target_package_id is None:
                return Failure("invalid_offer", "Paid conversion requires a target package.")
            count = await session.scalar(select(func.count(FreeTrialUpgradeORM.id)).where(FreeTrialUpgradeORM.vpn_key_id == vpn_key_id, FreeTrialUpgradeORM.status == _FULFILLED))
            if offer.max_purchases_per_trial is not None and int(count or 0) >= offer.max_purchases_per_trial:
                return Failure("offer_limit_reached", "This upgrade offer has reached its purchase limit for this trial.")
            claim = (await session.execute(select(FreeTrialClaimORM).where(FreeTrialClaimORM.vpn_key_id == vpn_key_id))).scalar_one_or_none()
            package_id = offer.target_package_id or key.package_id or 0
            public_order_id = "ORD-" + secrets.token_urlsafe(10)
            now = datetime.now(timezone.utc)
            order = OrderORM(
                user_id=user_id, package_id=package_id, public_order_id=public_order_id,
                checkout_token=idempotency_key, status=OrderORM.STATUS_WAITING_PAYMENT,
                payment_status=OrderORM.PAYMENT_UNPAID, currency=offer.currency,
                subtotal_amount=offer.price, discount_amount=Decimal("0"), total_amount=offer.price,
                amount=offer.price, package_name_snapshot=offer.name,
                package_type_snapshot="free_trial_upgrade", price_snapshot=offer.price,
                metadata_json={"kind": "free_trial_upgrade", "upgrade_type": offer.upgrade_type, "offer_id": offer.id, "vpn_key_id": vpn_key_id, "claim_id": claim.id if claim else None},
                expires_at=now + timedelta(minutes=30),
            )
            session.add(order)
            await session.flush()
            upgrade = FreeTrialUpgradeORM(
                public_upgrade_id="UPG-" + secrets.token_urlsafe(10), user_id=user_id,
                vpn_key_id=vpn_key_id, claim_id=claim.id if claim else None, offer_id=offer.id,
                order_id=order.id, idempotency_key=idempotency_key, upgrade_type=offer.upgrade_type,
                price_snapshot=offer.price, currency_snapshot=offer.currency,
                data_bytes_snapshot=int(offer.additional_data_bytes or 0),
                duration_seconds_snapshot=int(offer.additional_duration_seconds or 0),
                target_package_id_snapshot=offer.target_package_id,
                status=_PAYMENT_PENDING,
            )
            session.add(upgrade)
            await session.flush()
            result = {"upgrade_id": upgrade.id, "public_upgrade_id": upgrade.public_upgrade_id, "order_id": order.id, "public_order_id": order.public_order_id, "status": upgrade.status}
        await bus.emit(EventType.FREE_TRIAL_UPGRADE_ORDER_CREATED, user_id=user_id, upgrade_id=result["public_upgrade_id"], order_id=result["public_order_id"], upgrade_type=offer.upgrade_type)
        return Success(result)

    async def fulfill_paid_upgrade(self, *, order_id: int):
        async with self.db.session() as session:
            upgrade = (await session.execute(select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.order_id == order_id).with_for_update())).scalar_one_or_none()
            order = await session.get(OrderORM, order_id, with_for_update=True)
            if upgrade is None or order is None:
                return Failure("not_found", "Upgrade order was not found.")
            if upgrade.status == _FULFILLED:
                return Success(self._fulfillment_value(upgrade))
            if order.payment_status != OrderORM.PAYMENT_PAID:
                return Failure("payment_pending", "Payment has not been confirmed.")
            upgrade.status = _FULFILLMENT_PENDING
            key = await session.get(VPNKeyORM, upgrade.vpn_key_id, with_for_update=True)
            if key is None or key.user_id != upgrade.user_id:
                upgrade.status = "failed"; upgrade.error_code = "key_not_found"
                return Failure("not_found", "Trial VPN key was not found.")
            if upgrade.target_data_bytes is None and upgrade.upgrade_type in {DATA_ADDON, DATA_AND_DURATION}:
                upgrade.target_data_bytes = int(key.data_limit_bytes or 0) + int(upgrade.data_bytes_snapshot or 0)
            if upgrade.target_expires_at is None and upgrade.upgrade_type in {DURATION_EXTENSION, DATA_AND_DURATION}:
                base = key.expires_at or datetime.now(timezone.utc)
                upgrade.target_expires_at = base + timedelta(seconds=int(upgrade.duration_seconds_snapshot or 0))
            target_data = upgrade.target_data_bytes
            target_expiry = upgrade.target_expires_at
            user_id = upgrade.user_id; key_id = upgrade.vpn_key_id; upgrade_type = upgrade.upgrade_type
        await bus.emit(EventType.FREE_TRIAL_UPGRADE_FULFILLMENT_STARTED, order_id=order_id, upgrade_type=upgrade_type)
        if target_data is not None and not upgrade.data_applied:
            result = await self.data_limit.apply_for_key(key_id=key_id, actor_user_id=user_id, requested_limit_bytes=target_data, operation_id=f"upgrade:{order_id}:data")
            if result.is_failure:
                await self._mark_pending_failure(order_id, result.error.code, result.error.message)
                return result
            await self._mark_component(order_id, data=True)
        if target_expiry is not None and not upgrade.duration_applied:
            if self.lifecycle is None:
                return await self._mark_pending_failure(order_id, "lifecycle_unavailable", "VPN lifecycle service is unavailable.")
            result = await self.lifecycle.extend_key_to(key_id=key_id, actor_user_id=user_id, target_expires_at=target_expiry)
            if result.is_failure:
                await self._mark_pending_failure(order_id, result.error.code, result.error.message)
                return result
            await self._mark_component(order_id, duration=True)
        return await self._complete_upgrade(order_id)

    async def convert_to_paid_plan(self, *, user_id: int, vpn_key_id: int, offer_id: int, idempotency_key: str):
        return await self.create_upgrade_order(user_id=user_id, vpn_key_id=vpn_key_id, offer_id=offer_id, idempotency_key=idempotency_key)

    async def get_existing_fulfillment(self, *, order_id: int):
        async with self.db.session() as session:
            row = (await session.execute(select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.order_id == order_id))).scalar_one_or_none()
            return Success(self._fulfillment_value(row)) if row else Failure("not_found", "Upgrade fulfillment was not found.")

    async def get_upgrade_history(self, *, user_id: int, vpn_key_id: int | None = None):
        async with self.db.session() as session:
            query = select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.user_id == user_id).order_by(FreeTrialUpgradeORM.created_at.desc())
            if vpn_key_id is not None: query = query.where(FreeTrialUpgradeORM.vpn_key_id == vpn_key_id)
            return Success(list((await session.execute(query)).scalars().all()))

    async def recover_pending_fulfillment(self, *, limit: int = 50):
        async with self.db.session() as session:
            rows = list((await session.execute(select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.status == _FULFILLMENT_PENDING).order_by(FreeTrialUpgradeORM.created_at.asc()).limit(limit))).scalars().all())
        recovered = 0
        for row in rows:
            result = await self.fulfill_paid_upgrade(order_id=row.order_id)
            if result.is_success: recovered += 1
        return Success(recovered)

    async def _mark_component(self, order_id: int, *, data: bool = False, duration: bool = False):
        async with self.db.session() as session:
            row = (await session.execute(select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.order_id == order_id).with_for_update())).scalar_one()
            if data: row.data_applied = True
            if duration: row.duration_applied = True

    async def _mark_pending_failure(self, order_id: int, code: str, message: str):
        async with self.db.session() as session:
            row = (await session.execute(select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.order_id == order_id).with_for_update())).scalar_one_or_none()
            if row: row.status = _FULFILLMENT_PENDING; row.error_code = code; row.error_message = message[:500]
        await bus.emit(EventType.FREE_TRIAL_UPGRADE_FULFILLMENT_FAILED, order_id=order_id, code=code)
        return Failure(code, message)

    async def _complete_upgrade(self, order_id: int):
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            row = (await session.execute(select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.order_id == order_id).with_for_update())).scalar_one()
            order = await session.get(OrderORM, order_id, with_for_update=True)
            key = await session.get(VPNKeyORM, row.vpn_key_id, with_for_update=True)
            row.status = _FULFILLED; row.fulfilled_at = now; row.error_code = None; row.error_message = None
            order.status = OrderORM.STATUS_COMPLETED; order.completed_at = now; order.vpn_key_id = key.id
            if row.upgrade_type == PAID_PLAN_CONVERSION:
                key.key_type = "paid"; key.package_id = row.target_package_id_snapshot or key.package_id
            value = self._fulfillment_value(row)
        await bus.emit(EventType.FREE_TRIAL_UPGRADE_FULFILLED, order_id=order_id, upgrade_id=value["upgrade_id"], vpn_key_id=value["vpn_key_id"])
        if row.upgrade_type == PAID_PLAN_CONVERSION:
            await bus.emit(EventType.FREE_TRIAL_CONVERTED_TO_PAID, order_id=order_id, vpn_key_id=value["vpn_key_id"])
        return Success(value)

    @staticmethod
    def _fulfillment_value(row):
        return {"upgrade_id": row.public_upgrade_id, "order_id": row.order_id, "vpn_key_id": row.vpn_key_id, "upgrade_type": row.upgrade_type, "status": row.status, "data_applied": row.data_applied, "duration_applied": row.duration_applied}

    @staticmethod
    async def _order_summary(session, order_id):
        order = await session.get(OrderORM, order_id)
        return {"order_id": order.id, "public_order_id": order.public_order_id, "status": order.status, "payment_status": order.payment_status} if order else None
