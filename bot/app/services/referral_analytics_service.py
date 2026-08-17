"""Read-only Phase 6.5 referral, growth, reward, and risk analytics."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.result import Failure, Success
from database.models.order import OrderORM
from database.models.promo import PromoCodeORM, PromoRedemptionORM
from database.models.referral import ReferralORM
from database.models.referral_reward import ReferralRewardORM
from database.models.referral_risk_observation import ReferralRiskObservationORM
from database.models.user import UserORM


class ReferralAnalyticsService:
    """Admin-only analytics over authoritative Phase 6.1–6.4 records.

    This service never mutates referral, reward, promo, wallet, or order state.
    It intentionally keeps reward units separate instead of inventing a single
    incompatible monetary valuation.
    """

    def __init__(self, db, settings_service=None):
        self.db = db
        self.settings = settings_service

    async def _period(self, *, start=None, end=None, period="last_30_days"):
        now = datetime.now(timezone.utc)
        if start is not None and end is not None:
            return self._aware(start), self._aware(end)
        timezone_name = "Asia/Yangon"
        if self.settings is not None:
            timezone_name = str(await self.settings.get("timezone", timezone_name))
        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = timezone.utc
        local_now = now.astimezone(tz)
        if period == "today":
            local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "yesterday":
            local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            return local_start.astimezone(timezone.utc), (local_start + timedelta(days=1)).astimezone(timezone.utc)
        elif period == "last_7_days":
            local_start = local_now - timedelta(days=7)
        elif period == "this_month":
            local_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "previous_month":
            this_month = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            local_end = this_month
            previous_day = this_month - timedelta(days=1)
            local_start = previous_day.replace(day=1)
            return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)
        elif period == "all_time":
            return datetime(1970, 1, 1, tzinfo=timezone.utc), now
        else:
            local_start = local_now - timedelta(days=30)
        return local_start.astimezone(timezone.utc), now if end is None else self._aware(end)

    @staticmethod
    def _aware(value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    async def _admin(self, session, actor_user_id: int) -> bool:
        actor = await session.get(UserORM, actor_user_id)
        return actor is not None and actor.is_active and actor.role == "admin"

    async def dashboard(self, *, actor_user_id: int, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            referral_filter = (ReferralORM.created_at >= start, ReferralORM.created_at < end)
            total = int(await session.scalar(select(func.count(ReferralORM.id)).where(*referral_filter)) or 0)
            qualified = int(await session.scalar(select(func.count(ReferralORM.id)).where(ReferralORM.status.in_((ReferralORM.STATUS_QUALIFIED, ReferralORM.STATUS_REWARDED)), *referral_filter)) or 0)
            pending = int(await session.scalar(select(func.count(ReferralORM.id)).where(ReferralORM.status.in_((ReferralORM.STATUS_ATTRIBUTED, ReferralORM.STATUS_PENDING_QUALIFICATION)), *referral_filter)) or 0)
            invalid = int(await session.scalar(select(func.count(ReferralORM.id)).where(ReferralORM.status == ReferralORM.STATUS_INVALID, *referral_filter)) or 0)
            review = int(await session.scalar(select(func.count(ReferralORM.id)).where(ReferralORM.review_required.is_(True), *referral_filter)) or 0)
            rewards = int(await session.scalar(select(func.count(ReferralRewardORM.id)).where(ReferralRewardORM.source_type == "referral", ReferralRewardORM.status == ReferralRewardORM.STATUS_GRANTED, ReferralRewardORM.created_at >= start, ReferralRewardORM.created_at < end)) or 0)
            paid = int(await session.scalar(select(func.count(func.distinct(ReferralORM.referred_id))).select_from(ReferralORM).join(OrderORM, OrderORM.user_id == ReferralORM.referred_id).where(OrderORM.payment_status == OrderORM.PAYMENT_PAID, OrderORM.status.in_((OrderORM.STATUS_PAID, OrderORM.STATUS_COMPLETED)), *referral_filter)) or 0)
        return Success({"period": {"start": start, "end": end}, "overview": {"attributed": total, "qualified": qualified, "pending": pending, "invalid": invalid, "under_review": review, "rewards_granted": rewards, "paid_conversions": paid}, "funnel": await self.get_referral_funnel(actor_user_id=actor_user_id, start=start, end=end), "reward_summary": await self.get_reward_summary(actor_user_id=actor_user_id, start=start, end=end), "risk_summary": await self.get_risk_stats(actor_user_id=actor_user_id, start=start, end=end)})

    async def get_referral_funnel(self, *, actor_user_id: int, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(ReferralORM).where(ReferralORM.created_at >= start, ReferralORM.created_at < end))).scalars().all())
            attributed = len(rows)
            registered = len({row.referred_id for row in rows})
            force_join = sum(row.qualification_state not in {ReferralORM.QUALIFICATION_PENDING_FORCE_JOIN} for row in rows)
            trial = sum(row.qualification_state not in {ReferralORM.QUALIFICATION_PENDING_FREE_TRIAL} for row in rows)
            qualified = sum(row.status in {ReferralORM.STATUS_QUALIFIED, ReferralORM.STATUS_REWARDED} for row in rows)
            reward_eligible = sum(row.status in {ReferralORM.STATUS_QUALIFIED, ReferralORM.STATUS_REWARDED} and not row.review_required for row in rows)
            rewarded_ids = {row.referral_id for row in (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.source_type == "referral", ReferralRewardORM.status == ReferralRewardORM.STATUS_GRANTED, ReferralRewardORM.created_at >= start, ReferralRewardORM.created_at < end))).scalars().all()}
            granted = sum(row.id in rewarded_ids for row in rows)
        return {"period": {"start": start, "end": end}, "stages": [{"name": "attributed", "count": attributed}, {"name": "registered", "count": registered}, {"name": "force_join_completed", "count": force_join}, {"name": "free_trial_activated", "count": trial}, {"name": "qualified", "count": qualified}, {"name": "reward_eligible", "count": reward_eligible}, {"name": "reward_granted", "count": granted}], "rates": {"attribution_to_qualification_percent": self._rate(qualified, attributed), "qualification_to_reward_percent": self._rate(granted, qualified)}}

    async def get_reward_summary(self, *, actor_user_id: int, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.created_at >= start, ReferralRewardORM.created_at < end))).scalars().all())
        by_source = defaultdict(lambda: {"count": 0, "granted": 0, "failed": 0, "held": 0, "limit_reached": 0, "types": defaultdict(lambda: {"count": 0, "value": "0"})})
        for row in rows:
            item = by_source[row.source_type]
            item["count"] += 1
            if row.status == ReferralRewardORM.STATUS_GRANTED:
                item["granted"] += 1
            elif row.status == ReferralRewardORM.STATUS_FAILED:
                item["failed"] += 1
            elif row.status == ReferralRewardORM.STATUS_REVIEW_REQUIRED:
                item["held"] += 1
            elif row.status == ReferralRewardORM.STATUS_LIMIT_REACHED:
                item["limit_reached"] += 1
            type_item = item["types"][row.reward_type]
            type_item["count"] += 1
            type_item["value"] = str(Decimal(type_item["value"]) + Decimal(str(row.reward_value)))
        return {"period": {"start": start, "end": end}, "by_source": self._plain(by_source)}

    async def get_top_referrers(self, *, actor_user_id: int, sort_by="qualified", limit=20, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            referrals = list((await session.execute(select(ReferralORM).where(ReferralORM.created_at >= start, ReferralORM.created_at < end))).scalars().all())
            rewards = list((await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.source_type == "referral", ReferralRewardORM.created_at >= start, ReferralRewardORM.created_at < end))).scalars().all())
            orders = list((await session.execute(select(OrderORM).where(OrderORM.payment_status == OrderORM.PAYMENT_PAID, OrderORM.status.in_((OrderORM.STATUS_PAID, OrderORM.STATUS_COMPLETED)), OrderORM.created_at >= start, OrderORM.created_at < end))).scalars().all())
        metrics = defaultdict(lambda: {"attributed": 0, "qualified": 0, "paid_conversions": 0, "rewards_granted": 0})
        referred_to_referrer = {row.referred_id: row.referrer_id for row in referrals}
        for row in referrals:
            metrics[row.referrer_id]["attributed"] += 1
            metrics[row.referrer_id]["qualified"] += row.status in {ReferralORM.STATUS_QUALIFIED, ReferralORM.STATUS_REWARDED}
        for row in orders:
            referrer_id = referred_to_referrer.get(row.user_id)
            if referrer_id is not None:
                metrics[referrer_id]["paid_conversions"] += 1
        for row in rewards:
            if row.status == ReferralRewardORM.STATUS_GRANTED:
                referral = next((ref for ref in referrals if ref.id == row.referral_id), None)
                if referral:
                    metrics[referral.referrer_id]["rewards_granted"] += 1
        key = sort_by if sort_by in {"attributed", "qualified", "paid_conversions", "rewards_granted"} else "qualified"
        result = [{"referrer_id": user_id, **values, "qualification_rate_percent": self._rate(values["qualified"], values["attributed"])} for user_id, values in metrics.items()]
        return sorted(result, key=lambda item: (item[key], item["qualified"], item["attributed"]), reverse=True)[: max(1, min(100, int(limit)))]

    async def get_qualification_stats(self, *, actor_user_id: int, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(ReferralORM).where(ReferralORM.created_at >= start, ReferralORM.created_at < end))).scalars().all())
        counts = defaultdict(int)
        for row in rows:
            counts[row.qualification_state or row.status] += 1
        return {"period": {"start": start, "end": end}, "states": dict(counts)}

    async def get_limit_hit_stats(self, *, actor_user_id: int, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.status == ReferralRewardORM.STATUS_LIMIT_REACHED, ReferralRewardORM.created_at >= start, ReferralRewardORM.created_at < end))).scalars().all())
        counts = defaultdict(int)
        for row in rows:
            counts[row.limit_result or "unknown"] += 1
        return {"period": {"start": start, "end": end}, "limits": dict(counts), "total": len(rows)}

    async def get_risk_stats(self, *, actor_user_id: int, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(ReferralRiskObservationORM).where(ReferralRiskObservationORM.observed_at >= start, ReferralRiskObservationORM.observed_at < end))).scalars().all())
        by_signal = defaultdict(int)
        by_level = defaultdict(int)
        by_action = defaultdict(int)
        for row in rows:
            by_signal[row.signal_type] += 1
            by_level[row.risk_level] += 1
            by_action[row.action] += 1
        return {"period": {"start": start, "end": end}, "total": len(rows), "open": sum(row.status == ReferralRiskObservationORM.STATUS_OPEN for row in rows), "signals": dict(by_signal), "levels": dict(by_level), "actions": dict(by_action)}

    async def get_time_series(self, *, actor_user_id: int, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(ReferralORM).where(ReferralORM.created_at >= start, ReferralORM.created_at < end))).scalars().all())
        series = defaultdict(lambda: {"attributed": 0, "qualified": 0, "invalid": 0, "review": 0})
        for row in rows:
            day = self._aware(row.created_at).date().isoformat()
            series[day]["attributed"] += 1
            series[day]["qualified"] += row.status in {ReferralORM.STATUS_QUALIFIED, ReferralORM.STATUS_REWARDED}
            series[day]["invalid"] += row.status == ReferralORM.STATUS_INVALID
            series[day]["review"] += bool(row.review_required)
        return {"period": {"start": start, "end": end}, "points": [{"date": day, **series[day]} for day in sorted(series)]}

    async def get_user_referral_summary(self, *, actor_user_id: int, user_id: int, start=None, end=None, period="all_time"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            referrals = list((await session.execute(select(ReferralORM).where(ReferralORM.referrer_id == user_id, ReferralORM.created_at >= start, ReferralORM.created_at < end))).scalars().all())
            rewards = list((await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.beneficiary_user_id == user_id, ReferralRewardORM.created_at >= start, ReferralRewardORM.created_at < end))).scalars().all())
        return {"user_id": user_id, "period": {"start": start, "end": end}, "attributed": len(referrals), "qualified": sum(row.status in {ReferralORM.STATUS_QUALIFIED, ReferralORM.STATUS_REWARDED} for row in referrals), "pending": sum(row.status in {ReferralORM.STATUS_ATTRIBUTED, ReferralORM.STATUS_PENDING_QUALIFICATION} for row in referrals), "invalid": sum(row.status == ReferralORM.STATUS_INVALID for row in referrals), "review": sum(row.review_required for row in referrals), "rewards_granted": sum(row.status == ReferralRewardORM.STATUS_GRANTED for row in rewards), "reward_blocked": False}

    async def get_campaign_summary(self, *, actor_user_id: int, start=None, end=None, period="last_30_days"):
        start, end = await self._period(start=start, end=end, period=period)
        async with self.db.session() as session:
            if not await self._admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(PromoRedemptionORM).where(PromoRedemptionORM.created_at >= start, PromoRedemptionORM.created_at < end))).scalars().all())
            campaigns = {row.id: row for row in (await session.execute(select(PromoCodeORM))).scalars().all()}
        counts = defaultdict(lambda: {"redemptions": 0, "completed": 0, "failed": 0})
        for row in rows:
            item = counts[row.promo_code_id]
            item["redemptions"] += 1
            item["completed"] += row.status == "completed"
            item["failed"] += row.status == "failed"
        return {"period": {"start": start, "end": end}, "campaigns": [{"promo_code_id": code_id, "code": campaigns.get(code_id).display_code if campaigns.get(code_id) else None, **values} for code_id, values in counts.items()]}

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return round((numerator / denominator) * 100, 2) if denominator else 0.0

    @staticmethod
    def _plain(value):
        if isinstance(value, defaultdict):
            return {key: ReferralAnalyticsService._plain(item) for key, item in value.items()}
        if isinstance(value, dict):
            return {key: ReferralAnalyticsService._plain(item) for key, item in value.items()}
        return value
