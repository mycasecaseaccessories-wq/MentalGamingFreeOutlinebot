"""Typed, server-side mission condition validation and evaluation."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from database.models.mission import MissionORM


class MissionConditionService:
    MISSION_TYPES = {
        MissionORM.TYPE_JOIN_CHANNEL,
        MissionORM.TYPE_QUALIFIED_REFERRAL_COUNT,
        MissionORM.TYPE_FREE_TRIAL_ACTIVATED,
        MissionORM.TYPE_FIRST_PAID_PURCHASE,
        MissionORM.TYPE_PAID_PURCHASE_COUNT,
        MissionORM.TYPE_PURCHASE_AMOUNT,
        MissionORM.TYPE_VPN_RENEWAL,
        MissionORM.TYPE_DAILY_CHECK_IN,
        MissionORM.TYPE_WALLET_USAGE,
        MissionORM.TYPE_CUSTOM_EVENT,
    }
    REPEAT_MODES = {
        MissionORM.REPEAT_ONE_TIME,
        MissionORM.REPEAT_DAILY,
        MissionORM.REPEAT_WEEKLY,
        MissionORM.REPEAT_MONTHLY,
        MissionORM.REPEAT_REPEATABLE,
        MissionORM.REPEAT_EVENT_WINDOW,
    }
    REWARD_TYPES = {
        MissionORM.REWARD_NONE,
        MissionORM.REWARD_EXTRA_TRIAL,
        MissionORM.REWARD_WALLET_CREDIT,
        MissionORM.REWARD_BONUS_DATA,
        MissionORM.REWARD_BONUS_DURATION,
        MissionORM.REWARD_PROMO_ENTITLEMENT,
    }

    EVENT_MAP = {
        MissionORM.TYPE_JOIN_CHANNEL: {"force_join.satisfied", "mission.join_channel"},
        MissionORM.TYPE_QUALIFIED_REFERRAL_COUNT: {"referral.qualified"},
        MissionORM.TYPE_FREE_TRIAL_ACTIVATED: {"free_trial.provisioned", "provision.completed", "free_trial.activated"},
        MissionORM.TYPE_FIRST_PAID_PURCHASE: {"order.completed", "order.paid"},
        MissionORM.TYPE_PAID_PURCHASE_COUNT: {"order.completed", "order.paid"},
        MissionORM.TYPE_PURCHASE_AMOUNT: {"order.completed", "order.paid"},
        MissionORM.TYPE_VPN_RENEWAL: {"vpn.renewed", "vpn.renewal_completed", "order.completed"},
        MissionORM.TYPE_DAILY_CHECK_IN: {"mission.daily_check_in"},
        MissionORM.TYPE_WALLET_USAGE: {"wallet.payment_completed", "wallet.debited"},
        MissionORM.TYPE_CUSTOM_EVENT: set(),
    }

    @classmethod
    def validate_condition_config(cls, mission_type: str, config: dict[str, Any] | None) -> dict[str, Any]:
        if mission_type not in cls.MISSION_TYPES:
            raise ValueError("unsupported_mission_type")
        if config is None or not isinstance(config, dict):
            raise ValueError("condition_config_must_be_object")
        if any(isinstance(value, str) and ("__" in value or "lambda" in value.lower()) for value in config.values()):
            raise ValueError("executable_condition_not_allowed")
        if mission_type == MissionORM.TYPE_JOIN_CHANNEL and not config.get("chat_id") and not config.get("target_chat_id"):
            raise ValueError("join_channel_requires_chat_id")
        if mission_type == MissionORM.TYPE_CUSTOM_EVENT and not isinstance(config.get("event_name"), str):
            raise ValueError("custom_event_requires_event_name")
        if mission_type == MissionORM.TYPE_PURCHASE_AMOUNT:
            try:
                amount = Decimal(str(config.get("amount")))
            except (InvalidOperation, TypeError):
                raise ValueError("purchase_amount_requires_amount") from None
            if amount <= 0 or not config.get("currency"):
                raise ValueError("purchase_amount_invalid")
        if mission_type == MissionORM.TYPE_WALLET_USAGE and config.get("min_amount") is not None:
            if Decimal(str(config["min_amount"])) <= 0:
                raise ValueError("wallet_usage_invalid_amount")
        return dict(config)

    @classmethod
    def event_matches(cls, mission: MissionORM, event_type: str, payload: dict[str, Any]) -> bool:
        if mission.mission_type == MissionORM.TYPE_CUSTOM_EVENT:
            return event_type == str((mission.condition_config or {}).get("event_name"))
        return event_type in cls.EVENT_MAP.get(mission.mission_type, set())

    @classmethod
    def delta_for_event(cls, mission: MissionORM, payload: dict[str, Any]) -> int:
        if mission.mission_type == MissionORM.TYPE_PURCHASE_AMOUNT:
            amount = Decimal(str(payload.get("amount", 0)))
            currency = str(payload.get("currency", ""))
            configured = mission.condition_config or {}
            if configured.get("currency") and currency.upper() != str(configured["currency"]).upper():
                return 0
            return max(0, int(amount))
        if mission.mission_type == MissionORM.TYPE_WALLET_USAGE:
            amount = Decimal(str(payload.get("amount", 0)))
            minimum = Decimal(str((mission.condition_config or {}).get("min_amount", 0)))
            return 1 if amount >= minimum else 0
        return 1

    @classmethod
    def is_complete(cls, progress_value: int, target_value: int) -> bool:
        return progress_value >= target_value
