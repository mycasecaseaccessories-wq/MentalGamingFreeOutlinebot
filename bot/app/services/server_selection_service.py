from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.server_selection import (
    CandidateRejection,
    EligibilityDecision,
    RejectionReason,
    SelectedServerResult,
    SelectionFailureCode,
    SelectionResult,
    ServerScore,
    ServerSelectionPolicy,
    ServerSelectionRequest,
)
from database.repositories.server_repository import ServerRepository
from .base import BaseService


class ServerEligibilityPolicy:
    def __init__(self, policy: ServerSelectionPolicy | None = None) -> None:
        self.policy = policy or ServerSelectionPolicy()

    def evaluate(self, row: Any, request: ServerSelectionRequest) -> EligibilityDecision:
        reasons: list[RejectionReason] = []
        server_id = getattr(row, "public_server_id", "")
        if server_id in request.exclude_server_ids:
            reasons.append(RejectionReason.EXCLUDED)
        if getattr(row, "archived_at", None) is not None:
            reasons.append(RejectionReason.ARCHIVED)
        if request.required_server_id and server_id != request.required_server_id:
            reasons.append(RejectionReason.SERVER_MISMATCH)
        if not getattr(row, "enabled", False) or not getattr(row, "is_active", False):
            reasons.append(RejectionReason.DISABLED)
        if getattr(row, "maintenance_mode", False) or getattr(row, "status", None) == "maintenance":
            reasons.append(RejectionReason.MAINTENANCE)
        row_provider = getattr(row, "provider_type", None)
        if request.provider_type and row_provider is not None and str(row_provider).lower() != str(request.provider_type).lower():
            reasons.append(RejectionReason.PROVIDER_MISMATCH)

        health = str(getattr(row, "health_status", "")).lower()
        if health in {"offline", "down"}:
            reasons.append(RejectionReason.OFFLINE)
        elif health == "unhealthy":
            reasons.append(RejectionReason.UNHEALTHY)
        elif health == "unknown" and not self.policy.allow_unknown_health:
            reasons.append(RejectionReason.UNKNOWN_HEALTH)
        elif health == "degraded" and not self.policy.allow_degraded:
            reasons.append(RejectionReason.UNHEALTHY)
        if getattr(row, "stale_data", False) and request.require_fresh and not self.policy.allow_stale_fallback:
            reasons.append(RejectionReason.STALE_DATA)

        if request.country_required and (getattr(row, "country_code", None) or "").upper() != request.country_required.upper():
            reasons.append(RejectionReason.COUNTRY_MISMATCH)

        capabilities = set(request.required_capabilities)
        capabilities.add(request.workload)
        for capability in capabilities:
            attribute = {"free_trial": "free_trial_enabled", "paid": "paid_enabled", "vip": "vip_enabled"}.get(capability, capability)
            if not getattr(row, attribute, False):
                reasons.append(RejectionReason.PLAN_UNSUPPORTED if capability == request.workload else RejectionReason.CAPABILITY_MISSING)

        if getattr(row, "max_users", None) is None:
            if not self.policy.allow_unknown_capacity:
                reasons.append(RejectionReason.CAPACITY_UNKNOWN)
        elif getattr(row, "current_users", 0) >= row.max_users * (1 - self.policy.capacity_headroom_percent / 100):
            reasons.append(RejectionReason.CAPACITY_USERS)
        if getattr(row, "max_keys", None) is not None and (getattr(row, "existing_key_count", 0) or 0) >= row.max_keys * (1 - self.policy.capacity_headroom_percent / 100):
            reasons.append(RejectionReason.CAPACITY_KEYS)
        if getattr(row, "traffic_limit_bytes", None) is None:
            if not self.policy.allow_unknown_traffic:
                reasons.append(RejectionReason.TRAFFIC_UNKNOWN)
        elif getattr(row, "used_traffic_bytes", 0) >= row.traffic_limit_bytes * (1 - self.policy.traffic_headroom_percent / 100):
            reasons.append(RejectionReason.TRAFFIC_LIMIT)
        return EligibilityDecision(not reasons, tuple(dict.fromkeys(reasons)))

    def is_eligible(self, row: Any, request: ServerSelectionRequest) -> bool:
        return self.evaluate(row, request).eligible

    def exclusion_reasons(self, row: Any, request: ServerSelectionRequest) -> tuple[RejectionReason, ...]:
        return self.evaluate(row, request).reasons


class ServerScoringService:
    def __init__(self, policy: ServerSelectionPolicy | None = None) -> None:
        self.policy = policy or ServerSelectionPolicy()

    def score(self, row: Any, request: ServerSelectionRequest) -> ServerScore:
        health = {"healthy": 100, "ok": 100, "degraded": 55}.get(str(getattr(row, "health_status", "")).lower(), 0)
        capacity = (1 - max(self._ratio(getattr(row, "current_users", None), getattr(row, "max_users", None)), self._ratio(getattr(row, "existing_key_count", None), getattr(row, "max_keys", None)))) * 100
        traffic = (1 - self._ratio(getattr(row, "used_traffic_bytes", None), getattr(row, "traffic_limit_bytes", None))) * 100
        priority = max(0, 100 - min(100, float(getattr(row, "priority", 100))))
        weight = min(100, max(0, float(getattr(row, "weight", 1))))
        country = self.policy.country_preference_bonus if request.preferred_country and (getattr(row, "country_code", None) or "").upper() == request.preferred_country.upper() else 0
        if request.preferred_server_id and getattr(row, "public_server_id", None) == request.preferred_server_id:
            country += self.policy.preferred_server_bonus
        freshness = 0 if getattr(row, "stale_data", False) else 100
        total = health * self.policy.health_weight + capacity * self.policy.capacity_weight + traffic * self.policy.traffic_weight + priority * self.policy.priority_weight + country + freshness * 0.05 + weight * 0.05
        return ServerScore(row.public_server_id, total, health, capacity, traffic, priority, country, freshness, weight)

    @staticmethod
    def _ratio(value: Any, limit: Any) -> float:
        return 0 if limit in (None, 0) else min(1, max(0, float(value or 0) / float(limit)))


class ServerSelectionService(BaseService):
    def __init__(self, db: Any, policy: ServerSelectionPolicy | None = None, eligibility: ServerEligibilityPolicy | None = None, scoring: ServerScoringService | None = None) -> None:
        # Pure row selection is intentionally usable without bootstrapping the DB.
        # The async select() path still requires a real DatabaseManager.
        if db is not None:
            super().__init__(db)
        else:
            self.db = None
        self.policy = policy or ServerSelectionPolicy()
        self.eligibility = eligibility or ServerEligibilityPolicy(self.policy)
        self.scoring = scoring or ServerScoringService(self.policy)

    def select_from_rows(self, rows: list[Any], request: ServerSelectionRequest) -> SelectionResult:
        rows = list(rows)
        fallback = False
        fallback_reason = None
        candidates = rows
        if request.preferred_country and not request.country_required:
            preferred = [row for row in rows if (getattr(row, "country_code", None) or "").upper() == request.preferred_country.upper()]
            if preferred:
                candidates = preferred
            elif request.allow_fallback:
                fallback, fallback_reason = True, "preferred_pool_unavailable"
        if request.preferred_server_id and not request.required_server_id and not any(getattr(row, "public_server_id", None) == request.preferred_server_id for row in candidates):
            if not request.allow_fallback:
                return SelectionResult(None, len(rows), 0, (), SelectionFailureCode.REQUIRED_SERVER_UNAVAILABLE)
            fallback, fallback_reason = True, "preferred_server_unavailable"

        rejected: list[CandidateRejection] = []
        scores: list[ServerScore] = []
        for row in candidates:
            decision = self.eligibility.evaluate(row, request)
            if not decision.eligible:
                rejected.append(CandidateRejection(row.public_server_id, decision.reasons))
            else:
                scores.append(self.scoring.score(row, request))
        scores.sort(key=lambda item: (-item.total_score, -item.health_score, -item.capacity_score, -item.traffic_score, item.priority_score, -item.weight, item.server_id))
        if not scores:
            failure = SelectionFailureCode.NO_ELIGIBLE_SERVER
            return SelectionResult(None, len(rows), 0, tuple(rejected), failure)
        best = scores[0]
        row = next(item for item in candidates if item.public_server_id == best.server_id)
        selected = SelectedServerResult(best.server_id, self.policy.strategy.value, best, fallback, fallback_reason, None, {"server_id": best.server_id, "country_code": getattr(row, "country_code", None), "selected_at": datetime.now(timezone.utc).isoformat(), "phase4_key_creation_allowed": False})
        return SelectionResult(selected, len(rows), len(scores), tuple(rejected))

    async def select(self, request: ServerSelectionRequest) -> SelectionResult:
        async with self.db.session() as session:
            rows = await ServerRepository(session).list_for_selection()
        return self.select_from_rows(rows, request)

# Phase 3.6 compatibility adapter for pure-row callers.
class ServerSelectionEngine:
    def __init__(self, policy=None):
        self._service = ServerSelectionService(db=None, policy=policy)

    def select(self, rows, request):
        return self._service.select_from_rows(rows, request)
