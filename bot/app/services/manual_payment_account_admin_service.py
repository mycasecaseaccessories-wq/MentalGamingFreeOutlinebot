"""Authorized administration of public manual-payment destinations."""

from __future__ import annotations

from typing import Any

from app.core.result import Failure, Result, Success
from app.models.manual_payment import ManualPaymentMethod
from app.services.admin_authorization_service import AdminAuthorizationService
from app.services.manual_payment_service import ManualPaymentService


class ManualPaymentAccountAdminService:
    """Mutate payment destinations only after fresh admin confirmation."""

    ACTION_TYPE = "payment_account.update"
    PERMISSION = "manage_payments"

    def __init__(
        self,
        db: Any,
        *,
        authorization: AdminAuthorizationService | None = None,
        manual_payment: ManualPaymentService | None = None,
    ) -> None:
        self.db = db
        self.authorization = authorization or AdminAuthorizationService(db)
        self.manual_payment = manual_payment or ManualPaymentService(db)

    async def update_methods(  # noqa: PLR0911
        self,
        *,
        actor_telegram_id: int,
        methods: list[dict[str, Any]],
        request_id: str,
        challenge_id: str | None,
        chat_type: str | None = None,
    ) -> Result[list[dict[str, Any]]]:
        if not request_id.strip() or not challenge_id:
            return Failure("confirmation_required", "A one-time confirmation is required.")
        if not methods or len(methods) > 32:
            return Failure("invalid_methods", "At least one and at most 32 methods are allowed.")
        parsed: list[ManualPaymentMethod] = []
        for raw in methods:
            if not isinstance(raw, dict):
                return Failure("invalid_method", "Payment method configuration is invalid.")
            method = ManualPaymentMethod.from_config(raw)
            if (
                method is None
                or (method.min_amount is not None and method.min_amount < 0)
                or (method.max_amount is not None and method.max_amount < 0)
            ):
                return Failure("invalid_method", "Payment method configuration is invalid.")
            if (
                method.min_amount is not None
                and method.max_amount is not None
                and method.min_amount > method.max_amount
            ):
                return Failure("invalid_method", "Payment method range is invalid.")
            parsed.append(method)
        ids = [method.method_id for method in parsed]
        if len(ids) != len(set(ids)):
            return Failure("duplicate_method", "Payment method IDs must be unique.")
        safe_methods = [method.public_fields() | {"enabled": method.enabled} for method in parsed]
        payload = {"methods": safe_methods, "request_id": request_id.strip()}
        confirmed = await self.authorization.consume_challenge(
            actor_telegram_id,
            public_id=challenge_id,
            action_type=self.ACTION_TYPE,
            permission=self.PERMISSION,
            target_type="manual_payment_config",
            target_safe_id="global",
            payload=payload,
            chat_type=chat_type,
        )
        if confirmed.is_failure:
            return confirmed
        await self.manual_payment.set_methods(safe_methods)
        return Success(safe_methods)
