from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ProvisioningSource(StrEnum):
    PAID_ORDER = "paid_order"
    FREE_TRIAL = "free_trial"
    PROMOTION = "promotion"
    REWARD = "reward"
    ADMIN = "admin"
    RESELLER = "reseller"


class VPNProvisioningStatus(StrEnum):
    PENDING = "pending"
    SELECTING_SERVER = "selecting_server"
    RESERVED = "reserved"
    CREATING_REMOTE_KEY = "creating_remote_key"
    REMOTE_KEY_CREATED = "remote_key_created"
    PERSISTING_LOCAL_KEY = "persisting_local_key"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATION_REQUIRED = "compensation_required"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ProvisioningFailureCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    PERMISSION_ERROR = "permission_error"
    NOT_FOUND = "not_found"
    ORDER_NOT_PAID = "order_not_paid"
    ORDER_ALREADY_PROVISIONED = "order_already_provisioned"
    IDEMPOTENCY_IN_PROGRESS = "idempotency_in_progress"
    NO_ELIGIBLE_SERVER = "no_eligible_server"
    RESERVATION_FAILED = "reservation_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    REMOTE_KEY_CREATION_FAILED = "remote_key_creation_failed"
    PERSISTENCE_FAILED = "persistence_failed"
    COMPENSATION_FAILED = "compensation_failed"
    PROVISIONING_UNKNOWN = "provisioning_unknown"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class VPNProvisioningRequest:
    user_id: int
    source_type: ProvisioningSource
    workload_type: str = "paid"
    order_id: int | None = None
    package_id: int | None = None
    country_policy: str = "auto"
    specific_server_id: str | None = None
    preferred_country: str | None = None
    requested_data_limit_bytes: int | None = None
    requested_duration_days: int | None = None
    requested_device_limit: int | None = None
    country_policy: str = "auto"
    specific_server_id: str | None = None
    preferred_country: str | None = None
    provider_type: str = "outline"
    requested_data_limit_bytes: int | None = None
    requested_duration_days: int | None = None
    requested_device_limit: int | None = None
    idempotency_key: str = ""
    request_reference: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    reserve_capacity: bool = True
    allow_fallback: bool = True
    max_server_attempts: int = 2

    def validate(self) -> None:
        if self.user_id <= 0 or not self.idempotency_key or not self.request_reference:
            raise ValueError("user_id, idempotency_key, and request_reference are required")
        if self.provider_type != "outline":
            raise ValueError("unsupported provider_type")
        if not 1 <= self.max_server_attempts <= 3:
            raise ValueError("max_server_attempts must be between 1 and 3")
        if self.requested_data_limit_bytes is not None and self.requested_data_limit_bytes < 0:
            raise ValueError("requested_data_limit_bytes must be non-negative")
        if self.requested_device_limit is not None and self.requested_device_limit < 1:
            raise ValueError("requested_device_limit must be positive")


@dataclass(frozen=True, slots=True)
class RemoteVPNKeyResult:
    provider_key_id: int
    access_url: str
    provider_type: str
    created_at: datetime
    safe_metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"RemoteVPNKeyResult(provider_key_id={self.provider_key_id}, provider_type={self.provider_type!r})"


@dataclass(frozen=True, slots=True)
class VPNProvisioningSuccess:
    operation_id: str
    vpn_key_id: int
    server_public_id: str
    provider_type: str
    provider_key_id: int
    access_url: str
    fallback_used: bool = False
