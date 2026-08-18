from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from sqlalchemy import func, select

from database.models.order import OrderORM
from database.models.promo import PromoCodeORM, PromoRedemptionORM
from app.services.promo_service import PromoService, normalize_code
from app.services.maintenance_service import MaintenanceService, MaintenanceBlockedError


class PromoRedemptionService:
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, db, promo_service: PromoService, reward_service=None, maintenance_service: MaintenanceService | None = None):
        self.db = db
        self.promos = promo_service
        self.rewards = reward_service
        self.maintenance_service = maintenance_service

    async def redeem(self, *, user_id: int, code: str, idempotency_key: str | None = None, order_id: int | None = None):
        if self.maintenance_service is not None:
            try:
                await self.maintenance_service.assert_operation_allowed("promos", "REDEEM")
            except MaintenanceBlockedError:
                return {"status": "maintenance_active", "failure_reason": "maintenance_active"}
        normalized = normalize_code(code)
        key = idempotency_key or f"promo:{normalized}:user:{user_id}:order:{order_id or 'immediate'}"
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            return await self._redeem_locked(user_id=user_id, normalized=normalized, key=key, order_id=order_id)

    async def _redeem_locked(self, *, user_id: int, normalized: str, key: str, order_id: int | None):
        reservation = await self._reserve(user_id=user_id, normalized=normalized, key=key, order_id=order_id)
        if reservation.get("terminal"):
            return reservation["result"]
        row_id = reservation["row_id"]
        promo_data = reservation["promo"]
        if promo_data["reward_type"] in {PromoCodeORM.REWARD_PERCENT_DISCOUNT, PromoCodeORM.REWARD_FIXED_DISCOUNT}:
            return await self._apply_discount(row_id=row_id, promo_data=promo_data, user_id=user_id, order_id=order_id)
        if self.rewards is None:
            return await self._fail(row_id, "reward_service_unavailable")
        await self._set_status(row_id, PromoRedemptionORM.STATUS_GRANTING)
        reward_type = {PromoCodeORM.REWARD_EXTRA_TRIAL: "extra_trial", PromoCodeORM.REWARD_WALLET_CREDIT: "wallet_credit", PromoCodeORM.REWARD_BONUS_DATA: "bonus_data", PromoCodeORM.REWARD_BONUS_DURATION: "bonus_duration"}.get(promo_data["reward_type"])
        if reward_type is None or promo_data["reward_type"] == PromoCodeORM.REWARD_NONE:
            return await self._complete(row_id, promo_data, reward_reference=None)
        try:
            result = await self.rewards.grant_reward(user_id=user_id, reward_type=reward_type, reward_value=Decimal(promo_data["reward_value"]), source_reference=reservation["public_redemption_id"], period_key="promo", policy_revision=reservation["policy_revision"], reward_expiry_seconds=promo_data["reward_expiry_seconds"], apply_limits=False, source_type="promo")
        except Exception:
            return await self._fail(row_id, "reward_exception")
        if result.get("status") != "granted":
            return await self._fail(row_id, result.get("failure_reason") or result.get("status") or "reward_failed")
        return await self._complete(row_id, promo_data, reward_reference=result.get("public_reward_id"))

    async def _reserve(self, *, user_id: int, normalized: str, key: str, order_id: int | None):
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            existing = (await session.execute(select(PromoRedemptionORM).where(PromoRedemptionORM.idempotency_key == key).with_for_update())).scalar_one_or_none()
            if existing is not None and existing.status == PromoRedemptionORM.STATUS_COMPLETED:
                return {"terminal": True, "result": self._result(existing)}
            promo = None
            if existing is not None:
                promo = (await session.execute(select(PromoCodeORM).where(PromoCodeORM.id == existing.promo_id).with_for_update())).scalar_one()
                if existing.status in {PromoRedemptionORM.STATUS_RESERVED, PromoRedemptionORM.STATUS_GRANTING, PromoRedemptionORM.STATUS_RETRYING}:
                    return {"terminal": False, "row_id": existing.id, "public_redemption_id": existing.public_redemption_id, "policy_revision": existing.policy_revision, "promo": self._promo_data(promo)}
                existing.status = PromoRedemptionORM.STATUS_RETRYING
                existing.attempt_count += 1
                existing.error_code = None
                existing.failed_at = None
                await session.flush()
                return {"terminal": False, "row_id": existing.id, "public_redemption_id": existing.public_redemption_id, "policy_revision": existing.policy_revision, "promo": self._promo_data(promo)}
            promo = (await session.execute(select(PromoCodeORM).where(PromoCodeORM.code_normalized == normalized).with_for_update())).scalar_one_or_none()
            if promo is None:
                return {"terminal": True, "result": {"status": "failed", "error_code": "invalid_promo_code"}}
            available, reason = await self.promos.is_available(promo, now)
            used = int(await session.scalar(select(func.count(PromoRedemptionORM.id)).where(PromoRedemptionORM.promo_id == promo.id, PromoRedemptionORM.user_id == user_id, PromoRedemptionORM.status.in_([PromoRedemptionORM.STATUS_RESERVED, PromoRedemptionORM.STATUS_GRANTING, PromoRedemptionORM.STATUS_COMPLETED, PromoRedemptionORM.STATUS_FAILED, PromoRedemptionORM.STATUS_RETRYING]))) or 0)
            if used >= promo.max_redemptions_per_user:
                return {"terminal": True, "result": {"status": "failed", "error_code": "already_used"}}
            if not available:
                return {"terminal": True, "result": {"status": "failed", "error_code": reason}}
            order = None
            if order_id is not None:
                order = (await session.execute(select(OrderORM).where(OrderORM.id == order_id, OrderORM.user_id == user_id).with_for_update())).scalar_one_or_none()
                if order is None:
                    return {"terminal": True, "result": {"status": "failed", "error_code": "order_not_found"}}
            eligible, reason, snapshot = await self.promos.evaluate_eligibility(user_id, promo, order=order, now=now)
            if not eligible:
                return {"terminal": True, "result": {"status": "failed", "error_code": reason}}
            if promo.max_redemptions is not None and promo.reserved_count >= promo.max_redemptions:
                promo.status = PromoCodeORM.STATUS_EXHAUSTED
                return {"terminal": True, "result": {"status": "failed", "error_code": "usage_limit_reached"}}
            promo.reserved_count += 1
            data = self._promo_data(promo)
            row = PromoRedemptionORM(public_redemption_id=self._public_id("RED"), promo_id=promo.id, user_id=user_id, order_id=order_id, status=PromoRedemptionORM.STATUS_RESERVED, idempotency_key=key, reservation_key=f"order:{order_id}" if order_id is not None else "immediate", policy_revision=promo.policy_revision, policy_snapshot=data, eligibility_snapshot=snapshot, discount_amount=Decimal("0"), reserved_at=now, attempt_count=1)
            session.add(row)
            await session.flush()
            return {"terminal": False, "row_id": row.id, "public_redemption_id": row.public_redemption_id, "policy_revision": row.policy_revision, "promo": data}

    async def _apply_discount(self, *, row_id: int, promo_data: dict, user_id: int, order_id: int | None):
        now = datetime.now(timezone.utc)
        if order_id is None:
            return await self._fail(row_id, "order_required")
        async with self.db.session() as session:
            order = (await session.execute(select(OrderORM).where(OrderORM.id == order_id, OrderORM.user_id == user_id).with_for_update())).scalar_one_or_none()
            row = (await session.execute(select(PromoRedemptionORM).where(PromoRedemptionORM.id == row_id).with_for_update())).scalar_one()
            if order is None or order.payment_status == OrderORM.PAYMENT_PAID or order.status in {OrderORM.STATUS_CANCELLED, OrderORM.STATUS_EXPIRED, OrderORM.STATUS_COMPLETED}:
                row.status = PromoRedemptionORM.STATUS_FAILED
                row.error_code = "order_not_discountable"
                row.failed_at = now
                return self._result(row)
            discount = self.calculate_discount_data(promo_data, Decimal(str(order.subtotal_amount)))
            row.discount_amount = discount
            row.status = PromoRedemptionORM.STATUS_COMPLETED
            row.completed_at = now
            order.discount_amount = discount
            order.total_amount = max(Decimal("0"), Decimal(str(order.subtotal_amount)) - discount)
            promo = (await session.execute(select(PromoCodeORM).where(PromoCodeORM.id == row.promo_id).with_for_update())).scalar_one()
            promo.completed_count += 1
            await session.flush()
            return self._result(row)

    async def _complete(self, row_id: int, promo_data: dict, reward_reference: str | None):
        async with self.db.session() as session:
            row = (await session.execute(select(PromoRedemptionORM).where(PromoRedemptionORM.id == row_id).with_for_update())).scalar_one()
            if row.status == PromoRedemptionORM.STATUS_COMPLETED:
                return self._result(row)
            row.status = PromoRedemptionORM.STATUS_COMPLETED
            row.reward_reference = reward_reference
            row.completed_at = datetime.now(timezone.utc)
            promo = (await session.execute(select(PromoCodeORM).where(PromoCodeORM.id == row.promo_id).with_for_update())).scalar_one()
            promo.completed_count += 1
            await session.flush()
            return self._result(row)

    async def _fail(self, row_id: int, error_code: str):
        async with self.db.session() as session:
            row = (await session.execute(select(PromoRedemptionORM).where(PromoRedemptionORM.id == row_id).with_for_update())).scalar_one()
            row.status = PromoRedemptionORM.STATUS_FAILED
            row.error_code = error_code
            row.failed_at = datetime.now(timezone.utc)
            await session.flush()
            return self._result(row)

    async def _set_status(self, row_id: int, status: str):
        async with self.db.session() as session:
            row = (await session.execute(select(PromoRedemptionORM).where(PromoRedemptionORM.id == row_id).with_for_update())).scalar_one()
            if row.status != PromoRedemptionORM.STATUS_COMPLETED:
                row.status = status
            await session.flush()

    async def history(self, user_id: int, limit: int = 20):
        async with self.db.session() as session:
            rows = (await session.execute(select(PromoRedemptionORM).where(PromoRedemptionORM.user_id == user_id).order_by(PromoRedemptionORM.created_at.desc()).limit(max(1, min(50, limit))))).scalars().all()
            return [self._result(row) for row in rows]

    async def retry(self, public_redemption_id: str):
        async with self.db.session() as session:
            row = (await session.execute(select(PromoRedemptionORM).where(PromoRedemptionORM.public_redemption_id == public_redemption_id))).scalar_one_or_none()
            if row is None:
                raise ValueError("redemption_not_found")
            promo = (await session.execute(select(PromoCodeORM).where(PromoCodeORM.id == row.promo_id))).scalar_one()
            user_id, key, order_id = row.user_id, row.idempotency_key, row.order_id
            code = promo.code_normalized
        return await self.redeem(user_id=user_id, code=code, idempotency_key=key, order_id=order_id)

    @staticmethod
    def calculate_discount_data(promo_data: dict, subtotal: Decimal) -> Decimal:
        subtotal = max(Decimal("0"), subtotal)
        value = Decimal(str(promo_data.get("reward_value", "0")))
        if promo_data.get("reward_type") == PromoCodeORM.REWARD_PERCENT_DISCOUNT:
            discount = subtotal * value / Decimal("100")
        elif promo_data.get("reward_type") == PromoCodeORM.REWARD_FIXED_DISCOUNT:
            discount = value
        else:
            return Decimal("0")
        return min(subtotal, max(Decimal("0"), discount)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    @staticmethod
    def _promo_data(row):
        return {"promo_id": row.id, "reward_type": row.reward_type, "reward_value": str(row.reward_value), "currency": row.currency, "reward_expiry_seconds": row.reward_expiry_seconds, "minimum_purchase_amount": str(row.minimum_purchase_amount) if row.minimum_purchase_amount is not None else None, "eligibility_policy": row.eligibility_policy, "policy_revision": row.policy_revision}

    @staticmethod
    def _public_id(prefix: str) -> str:
        return f"{prefix}-" + secrets.token_hex(7).upper()

    @staticmethod
    def _result(row):
        return {"public_redemption_id": row.public_redemption_id, "status": row.status, "promo_id": row.promo_id, "user_id": row.user_id, "order_id": row.order_id, "reward_reference": row.reward_reference, "discount_amount": str(row.discount_amount), "error_code": row.error_code, "policy_revision": row.policy_revision, "completed_at": row.completed_at}
