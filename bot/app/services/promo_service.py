from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from database.models.order import OrderORM
from database.models.promo import PromoCodeORM
from database.models.referral import ReferralORM
from database.models.user import UserORM


_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,63}$")
_ALLOWED_REWARDS = {
    PromoCodeORM.REWARD_EXTRA_TRIAL,
    PromoCodeORM.REWARD_WALLET_CREDIT,
    PromoCodeORM.REWARD_BONUS_DATA,
    PromoCodeORM.REWARD_BONUS_DURATION,
    PromoCodeORM.REWARD_PERCENT_DISCOUNT,
    PromoCodeORM.REWARD_FIXED_DISCOUNT,
    PromoCodeORM.REWARD_NONE,
}
_ALLOWED_ELIGIBILITY = {
    PromoCodeORM.ELIGIBILITY_ALL_ACTIVE,
    PromoCodeORM.ELIGIBILITY_NEW_USERS,
    PromoCodeORM.ELIGIBILITY_EXISTING_USERS,
    PromoCodeORM.ELIGIBILITY_PAID_USERS,
    PromoCodeORM.ELIGIBILITY_NEVER_PURCHASED,
    PromoCodeORM.ELIGIBILITY_FIRST_PURCHASE,
    PromoCodeORM.ELIGIBILITY_SPECIFIC_ROLE,
    PromoCodeORM.ELIGIBILITY_REFERRAL_USERS,
    PromoCodeORM.ELIGIBILITY_MISSION_COMPLETERS,
}


def normalize_code(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid_promo_code")
    normalized = value.strip().upper()
    if not _CODE_RE.fullmatch(normalized):
        raise ValueError("invalid_promo_code")
    return normalized


class PromoService:
    """Authoritative admin configuration and server-side promo policy service."""

    def __init__(self, db, settings_service=None):
        self.db = db
        self.settings = settings_service

    @staticmethod
    def _public_id(prefix: str) -> str:
        return f"{prefix}-" + secrets.token_urlsafe(8).replace("_", "-").replace("/", "-").upper()[:12]

    @staticmethod
    def _validate_config(*, reward_type: str, reward_value: Decimal, promo_type: str, max_redemptions: int | None, per_user: int, starts_at, expires_at, minimum_purchase_amount: Decimal | None, eligibility_policy: dict[str, Any] | None):
        if reward_type not in _ALLOWED_REWARDS:
            raise ValueError("unsupported_reward_type")
        if promo_type not in {PromoCodeORM.TYPE_REWARD, PromoCodeORM.TYPE_DISCOUNT, PromoCodeORM.TYPE_CAMPAIGN}:
            raise ValueError("unsupported_promo_type")
        if reward_value < 0 or (reward_type != PromoCodeORM.REWARD_NONE and reward_value <= 0):
            raise ValueError("invalid_reward_value")
        if reward_type in {PromoCodeORM.REWARD_PERCENT_DISCOUNT} and reward_value > 100:
            raise ValueError("invalid_discount_percentage")
        if max_redemptions is not None and max_redemptions < 1:
            raise ValueError("invalid_max_redemptions")
        if per_user < 1:
            raise ValueError("invalid_per_user_limit")
        if starts_at and expires_at and expires_at <= starts_at:
            raise ValueError("invalid_promo_window")
        if minimum_purchase_amount is not None and minimum_purchase_amount < 0:
            raise ValueError("invalid_minimum_purchase")
        policy = eligibility_policy or {"kind": PromoCodeORM.ELIGIBILITY_ALL_ACTIVE}
        kind = policy.get("kind", PromoCodeORM.ELIGIBILITY_ALL_ACTIVE)
        if kind not in _ALLOWED_ELIGIBILITY:
            raise ValueError("unsupported_eligibility")
        if kind == PromoCodeORM.ELIGIBILITY_SPECIFIC_ROLE and not policy.get("role"):
            raise ValueError("missing_eligibility_role")

    async def create_promo(self, *, name: str, code: str | None, reward_type: str, reward_value: Decimal | int | str, created_by: int | None = None, promo_type: str = PromoCodeORM.TYPE_REWARD, description: str | None = None, currency: str | None = None, starts_at=None, expires_at=None, max_redemptions: int | None = None, max_redemptions_per_user: int = 1, minimum_purchase_amount=None, eligibility_policy: dict[str, Any] | None = None, reward_expiry_seconds: int = 0, is_public: bool = True, status: str = PromoCodeORM.STATUS_DRAFT):
        normalized = normalize_code(code or self._public_id("PROMO").replace("PROMO-", "")[:12])
        value = Decimal(str(reward_value))
        minimum = Decimal(str(minimum_purchase_amount)) if minimum_purchase_amount is not None else None
        self._validate_config(reward_type=reward_type, reward_value=value, promo_type=promo_type, max_redemptions=max_redemptions, per_user=max_redemptions_per_user, starts_at=starts_at, expires_at=expires_at, minimum_purchase_amount=minimum, eligibility_policy=eligibility_policy)
        if reward_expiry_seconds < 0:
            raise ValueError("invalid_reward_expiry")
        async with self.db.session() as session:
            existing = (await session.execute(select(PromoCodeORM).where(PromoCodeORM.code_normalized == normalized))).scalar_one_or_none()
            if existing is not None:
                raise ValueError("promo_code_already_exists")
            row = PromoCodeORM(public_promo_id=self._public_id("PRM"), code_normalized=normalized, display_code=normalized, name=name[:128], description=description[:512] if description else None, promo_type=promo_type, status=status, reward_type=reward_type, reward_value=value, currency=currency.upper() if currency else None, reward_expiry_seconds=reward_expiry_seconds, starts_at=starts_at, expires_at=expires_at, max_redemptions=max_redemptions, max_redemptions_per_user=max_redemptions_per_user, minimum_purchase_amount=minimum, eligibility_policy=eligibility_policy or {"kind": PromoCodeORM.ELIGIBILITY_ALL_ACTIVE}, policy_revision=1, reward_policy_snapshot={"reward_type": reward_type, "reward_value": str(value), "reward_expiry_seconds": reward_expiry_seconds}, is_public=is_public, created_by=created_by)
            session.add(row)
            await session.flush()
            return self.to_dict(row)

    async def get_by_code(self, code: str):
        normalized = normalize_code(code)
        async with self.db.session() as session:
            return (await session.execute(select(PromoCodeORM).where(PromoCodeORM.code_normalized == normalized))).scalar_one_or_none()

    async def get_by_public_id(self, public_id: str):
        async with self.db.session() as session:
            return (await session.execute(select(PromoCodeORM).where(PromoCodeORM.public_promo_id == public_id))).scalar_one_or_none()

    async def list_promos(self, *, include_archived: bool = False):
        async with self.db.session() as session:
            query = select(PromoCodeORM).order_by(PromoCodeORM.created_at.desc())
            if not include_archived:
                query = query.where(PromoCodeORM.status != PromoCodeORM.STATUS_ARCHIVED)
            rows = (await session.execute(query)).scalars().all()
            return [self.to_dict(row) for row in rows]

    async def set_status(self, public_promo_id: str, status: str):
        if status not in {PromoCodeORM.STATUS_DRAFT, PromoCodeORM.STATUS_SCHEDULED, PromoCodeORM.STATUS_ACTIVE, PromoCodeORM.STATUS_PAUSED, PromoCodeORM.STATUS_DISABLED, PromoCodeORM.STATUS_ARCHIVED}:
            raise ValueError("unsupported_promo_status")
        async with self.db.session() as session:
            row = (await session.execute(select(PromoCodeORM).where(PromoCodeORM.public_promo_id == public_promo_id).with_for_update())).scalar_one_or_none()
            if row is None:
                raise ValueError("promo_not_found")
            if row.status == PromoCodeORM.STATUS_ARCHIVED and status != PromoCodeORM.STATUS_ARCHIVED:
                raise ValueError("archived_promo_immutable")
            row.status = status
            row.policy_revision += 1
            await session.flush()
            return self.to_dict(row)

    async def is_available(self, promo: PromoCodeORM, now=None) -> tuple[bool, str]:
        now = now or datetime.now(timezone.utc)
        if promo.status in {PromoCodeORM.STATUS_PAUSED, PromoCodeORM.STATUS_DISABLED, PromoCodeORM.STATUS_ARCHIVED, PromoCodeORM.STATUS_DRAFT}:
            return False, "promo_not_active"
        if promo.starts_at and _aware(promo.starts_at) > now:
            return False, "promo_not_active"
        if promo.expires_at and _aware(promo.expires_at) <= now:
            return False, "promo_expired"
        if promo.max_redemptions is not None and promo.reserved_count >= promo.max_redemptions:
            return False, "usage_limit_reached"
        return True, "eligible"

    async def evaluate_eligibility(self, user_id: int, promo: PromoCodeORM, *, order=None, now=None) -> tuple[bool, str, dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        async with self.db.session() as session:
            user = (await session.execute(select(UserORM).where(UserORM.id == user_id))).scalar_one_or_none()
            if user is None or not user.is_active or user.status in {"banned", "suspended"}:
                return False, "not_eligible", {"reason": "inactive"}
            policy = promo.eligibility_policy or {"kind": PromoCodeORM.ELIGIBILITY_ALL_ACTIVE}
            kind = policy.get("kind", PromoCodeORM.ELIGIBILITY_ALL_ACTIVE)
            if kind == PromoCodeORM.ELIGIBILITY_NEW_USERS and user.first_seen_at < now - timedelta(seconds=int(policy.get("max_first_seen_age_seconds", 86400))):
                return False, "not_eligible", {"reason": "new_user_only"}
            if kind == PromoCodeORM.ELIGIBILITY_EXISTING_USERS and user.first_seen_at >= now - timedelta(seconds=int(policy.get("min_first_seen_age_seconds", 86400))):
                return False, "not_eligible", {"reason": "existing_users_only"}
            if kind == PromoCodeORM.ELIGIBILITY_SPECIFIC_ROLE and user.role != policy.get("role"):
                return False, "not_eligible", {"reason": "role"}
            orders = select(OrderORM.id).where(OrderORM.user_id == user_id, OrderORM.payment_status == OrderORM.PAYMENT_PAID)
            paid_count = len((await session.execute(orders)).scalars().all())
            if kind == PromoCodeORM.ELIGIBILITY_PAID_USERS and paid_count == 0:
                return False, "not_eligible", {"reason": "paid_user_only"}
            if kind == PromoCodeORM.ELIGIBILITY_NEVER_PURCHASED and paid_count > 0:
                return False, "not_eligible", {"reason": "never_purchased"}
            if kind == PromoCodeORM.ELIGIBILITY_FIRST_PURCHASE and paid_count > 0:
                return False, "not_eligible", {"reason": "first_purchase_only"}
            if promo.minimum_purchase_amount is not None and (order is None or Decimal(str(order.subtotal_amount)) < Decimal(str(promo.minimum_purchase_amount))):
                return False, "minimum_purchase_not_met", {"reason": "minimum_purchase"}
            if order is not None and promo.currency and str(order.currency).upper() != promo.currency.upper():
                return False, "currency_mismatch", {"reason": "currency"}
            return True, "eligible", {"kind": kind, "paid_count": paid_count, "first_seen_at": user.first_seen_at.isoformat()}

    @staticmethod
    def to_dict(row: PromoCodeORM) -> dict[str, Any]:
        return {"public_promo_id": row.public_promo_id, "code": row.display_code, "status": row.status, "promo_type": row.promo_type, "reward_type": row.reward_type, "reward_value": str(row.reward_value), "currency": row.currency, "max_redemptions": row.max_redemptions, "reserved_count": row.reserved_count, "completed_count": row.completed_count, "max_redemptions_per_user": row.max_redemptions_per_user, "starts_at": row.starts_at, "expires_at": row.expires_at, "policy_revision": row.policy_revision}


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
