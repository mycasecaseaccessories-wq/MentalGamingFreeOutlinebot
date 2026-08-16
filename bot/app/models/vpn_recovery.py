from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    COMPLETED = "completed"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    FAILED = "failed"


class RotationReason(str, Enum):
    LOST = "lost"
    COMPROMISED = "compromised"
    DAMAGED = "damaged"
    ADMIN_REQUEST = "admin_request"


@dataclass(frozen=True)
class RenewalRequest:
    user_id: int
    key_id: int
    package_id: int
    payment_reference: str
    idempotency_key: str

    def validate(self) -> None:
        if self.user_id <= 0 or self.key_id <= 0 or self.package_id <= 0:
            raise ValueError("user_id, key_id, and package_id must be positive")
        if not self.payment_reference or not self.idempotency_key:
            raise ValueError("payment_reference and idempotency_key are required")


@dataclass(frozen=True)
class RotationRequest:
    user_id: int
    key_id: int
    reason: RotationReason
    idempotency_key: str

    def validate(self) -> None:
        if self.user_id <= 0 or self.key_id <= 0:
            raise ValueError("user_id and key_id must be positive")
        if not isinstance(self.reason, RotationReason):
            raise ValueError("reason must be a RotationReason")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
