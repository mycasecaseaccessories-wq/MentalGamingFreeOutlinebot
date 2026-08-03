"""
GrowthService — referral programme and affiliate tracking.

Responsibilities (Phase 5+):
  • Generate unique referral links / codes per user.
  • Track referred registrations.
  • Calculate and credit referral commissions.
  • Manage affiliate tiers and payout thresholds.
"""

from __future__ import annotations

from .base import BaseService


class GrowthService(BaseService):
    """Manages the referral and affiliate growth engine."""

    async def get_referral_code(self, telegram_id: int) -> str:
        """
        Return the unique referral code for the user, creating one if absent.

        Args:
            telegram_id: The referring user.
        """
        # TODO (Phase 5): call GrowthRepository.get_or_create_code()
        raise NotImplementedError("GrowthService.get_referral_code — Phase 5")

    async def track_referral(self, referral_code: str, new_user_id: int) -> None:
        """
        Record that new_user_id registered via the given referral_code.

        Args:
            referral_code: The code embedded in the /start deep-link.
            new_user_id:   Telegram ID of the newly registered user.
        """
        # TODO (Phase 5): resolve referrer, create referral record
        raise NotImplementedError("GrowthService.track_referral — Phase 5")

    async def get_referral_stats(self, telegram_id: int) -> dict:
        """
        Return referral statistics for the user.

        Returns:
            Dict with keys: total_referrals, total_earnings, pending_payout.
        """
        # TODO (Phase 5): aggregate from GrowthRepository
        raise NotImplementedError("GrowthService.get_referral_stats — Phase 5")
