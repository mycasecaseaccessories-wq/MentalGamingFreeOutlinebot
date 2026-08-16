from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkloadType(StrEnum):
    PAID = "paid"
    FREE_TRIAL = "free_trial"
    VIP = "vip"
    PROMOTION = "promotion"
    REWARD = "reward"
    RESELLER = "reseller"
    SYSTEM = "system"


class SelectionStrategy(StrEnum):
    PRIORITY_WEIGHTED = "priority_weighted"
    BEST_SCORE = "best_score"


class RejectionReason(StrEnum):
    DISABLED = "disabled"
    MAINTENANCE = "maintenance"
    ARCHIVED = "archived"
    OFFLINE = "offline"
    UNHEALTHY = "unhealthy"
    UNKNOWN_HEALTH = "unknown_health"
    STALE_DATA = "stale_data"
    PROVIDER_MISMATCH = "provider_mismatch"
    CAPABILITY_MISSING = "capability_missing"
    COUNTRY_MISMATCH = "country_mismatch"
    SERVER_MISMATCH = "server_mismatch"
    EXCLUDED = "excluded"
    CAPACITY_USERS = "capacity_users"
    CAPACITY_KEYS = "capacity_keys"
    CAPACITY_UNKNOWN = "capacity_unknown"
    TRAFFIC_LIMIT = "traffic_limit"
    TRAFFIC_UNKNOWN = "traffic_unknown"
    PLAN_UNSUPPORTED = "plan_unsupported"


class SelectionFailureCode(StrEnum):
    NO_ELIGIBLE_SERVER = "no_eligible_server"
    REQUIRED_SERVER_UNAVAILABLE = "required_server_unavailable"
    COUNTRY_UNAVAILABLE = "country_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    CAPACITY_EXHAUSTED = "capacity_exhausted"
    TRAFFIC_CAPACITY_EXHAUSTED = "traffic_capacity_exhausted"
    HEALTH_UNAVAILABLE = "health_unavailable"
    OPERATIONAL_DATA_STALE = "operational_data_stale"


@dataclass(frozen=True, slots=True)
class ServerSelectionRequest:
    workload_type: str = "paid"
    plan: str | None = None
    package_id: int | None = None
    country_code: str | None = None
    preferred_country: str | None = None
    required_country: str | None = None
    provider_type: str | None = "outline"
    required_capabilities: frozenset[str] = frozenset()
    preferred_server_id: str | None = None
    required_server_id: str | None = None
    allow_fallback: bool = False
    exclude_server_ids: frozenset[str] = frozenset()
    reservation_required: bool = False
    request_reference: str | None = None
    require_fresh: bool = True

    @property
    def workload(self) -> str:
        value = str(self.plan or self.workload_type).lower()
        return "free_trial" if value in {"free", "trial", "free_trial"} else value

    @property
    def country_required(self) -> str | None:
        return self.required_country or self.country_code


@dataclass(frozen=True, slots=True)
class ServerSelectionPolicy:
    strategy: SelectionStrategy = SelectionStrategy.PRIORITY_WEIGHTED
    allow_degraded: bool = False
    allow_unknown_health: bool = False
    allow_stale_fallback: bool = False
    allow_unknown_capacity: bool = False
    allow_unknown_traffic: bool = False
    capacity_headroom_percent: float = 10.0
    traffic_headroom_percent: float = 10.0
    health_weight: float = 0.35
    capacity_weight: float = 0.30
    traffic_weight: float = 0.20
    priority_weight: float = 0.10
    country_preference_bonus: float = 5.0
    preferred_server_bonus: float = 8.0


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible: bool
    reasons: tuple[RejectionReason, ...] = ()


@dataclass(frozen=True, slots=True)
class ServerScore:
    server_id: str
    total_score: float
    health_score: float
    capacity_score: float
    traffic_score: float
    priority_score: float
    country_score: float
    freshness_score: float
    weight: float
    safe_reasons: tuple[str, ...] = ()

    @property
    def total(self) -> float:
        return self.total_score


@dataclass(frozen=True, slots=True)
class CandidateRejection:
    server_id: str
    reasons: tuple[RejectionReason, ...]

    @property
    def reason(self) -> RejectionReason:
        return self.reasons[0]


@dataclass(frozen=True, slots=True)
class SelectedServerResult:
    server_id: str
    strategy: str
    score: ServerScore
    fallback_used: bool = False
    fallback_reason: str | None = None
    reservation_token: str | None = None
    handoff: dict[str, Any] = field(default_factory=dict)

    @property
    def country_code(self) -> str | None:
        return self.handoff.get("country_code")


@dataclass(frozen=True, slots=True)
class SelectionResult:
    selected: SelectedServerResult | None
    considered: int
    eligible: int
    rejected: tuple[CandidateRejection, ...] = ()
    failure_code: SelectionFailureCode | None = None

    @property
    def no_server_reason(self) -> str | None:
        return self.failure_code.value if self.failure_code else None


SelectionRequest = ServerSelectionRequest
