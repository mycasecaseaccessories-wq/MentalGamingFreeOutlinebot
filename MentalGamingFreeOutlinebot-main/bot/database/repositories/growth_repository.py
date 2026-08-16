"""
GrowthRepository — data access for the referrals table.

Tracks referral relationships and commission eligibility.
Used exclusively by GrowthService (Phase 5).
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.models.referral import ReferralORM
from .base import BaseRepository


class GrowthRepository(BaseRepository[ReferralORM, ReferralORM]):
    """
    Handles all database operations for the referrals table.

    Phase 0.2: CRUD inherited; referral lookup queries stubbed.
    Phase 5:   GrowthService creates referrals on registration and
               qualifies them on first successful purchase.
    """

    orm_class    = ReferralORM
    domain_class = ReferralORM

    async def get_by_referred_id(self, referred_id: int) -> Optional[ReferralORM]:
        """
        Return the referral record for a newly registered user.

        Args:
            referred_id: user primary key of the referred (new) user.
        """
        stmt = select(ReferralORM).where(ReferralORM.referred_id == referred_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_referrals_by_referrer(self, referrer_id: int) -> List[ReferralORM]:
        """
        Return all referral records where referrer_id is the referring user.

        Used to compute the total count and commission for a user's referral page.
        """
        stmt = select(ReferralORM).where(ReferralORM.referrer_id == referrer_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def qualify(
        self,
        referral_id: int,
        commission: float,
        currency: str,
    ) -> Optional[ReferralORM]:
        """
        Transition a referral to the 'qualified' status.

        Args:
            referral_id: Primary key of the ReferralORM row.
            commission:  Commission amount to credit to the referrer.
            currency:    ISO 4217 currency code.
        """
        from datetime import datetime, timezone
        return await self.update(
            referral_id,
            status=ReferralORM.STATUS_QUALIFIED,
            commission=commission,
            currency=currency,
            qualified_at=datetime.now(timezone.utc),
        )

    async def mark_rewarded(self, referral_id: int) -> Optional[ReferralORM]:
        """Mark a qualified referral as rewarded after commission is credited."""
        return await self.update(referral_id, status=ReferralORM.STATUS_REWARDED)
