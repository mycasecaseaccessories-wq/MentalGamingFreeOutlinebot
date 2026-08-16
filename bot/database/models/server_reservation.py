from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class ServerCapacityReservationORM(BaseModel):
    __tablename__ = "server_capacity_reservations"
    __table_args__ = (
        UniqueConstraint("public_reservation_id", name="uq_reservation_public_id"),
        UniqueConstraint("owner_reference", name="uq_reservation_owner_reference"),
        UniqueConstraint("claim_id", name="uq_reservation_claim_id"),
    )

    STATUS_PENDING = "pending"       # SERVER_RESERVED / in-flight
    STATUS_COMMITTED = "committed"   # consumed by Phase 5.5
    STATUS_RELEASED = "released"
    STATUS_EXPIRED = "expired"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_reservation_id: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False, index=True)
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("free_trial_claims.id", ondelete="RESTRICT"), nullable=True, index=True)
    workload_type: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_reference: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    period_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=STATUS_PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
