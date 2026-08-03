"""
FreeTrialORM — free trial allocations and usage tracking.

Tracks whether a user has already used their one-time free trial.
Prevents duplicate trial abuse.

Columns
-------
user_id       FK → users.id.
vpn_key_id    FK → vpn_keys.id — key issued for the trial.
duration_days How many days the trial lasts.
is_used       True once the trial has been activated.
expires_at    UTC timestamp when the trial key will be revoked.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class FreeTrialORM(BaseModel):
    """
    Free trial allocation record.

    Phase 0.2: schema placeholder.
    Phase 4:   VPNService checks this before issuing a trial key.
    """

    __tablename__ = "free_trials"

    user_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,           # One trial per user — enforced at DB level.
        nullable=False,
        index=True,
        comment="FK → users.id — one trial per user",
    )
    vpn_key_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="FK → vpn_keys.id — set when the trial key is issued",
    )
    duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Trial duration in days",
    )
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True once the trial has been activated",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the trial key auto-revokes",
    )
