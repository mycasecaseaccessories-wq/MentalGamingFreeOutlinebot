from __future__ import annotations

from app.core.result import Failure
from app.models.vpn_provisioning import ProvisioningSource, VPNProvisioningRequest
from .base import BaseService


class VPNProvisioningEntryService(BaseService):
    """Authorized manual entry points for Phase 4.1.

    Payment approval alone never calls this service. An admin or the owning
    customer must explicitly request provisioning after the order is paid.
    """

    MESSAGES = {
        "en": {
            "manual_required": "Payment approved. VPN key provisioning requires an explicit request.",
            "accepted": "VPN key provisioning request accepted.",
        },
        "my": {
            "manual_required": "ငွေပေးချေမှု အတည်ပြုပြီးပါပြီ။ VPN key ထုတ်ရန် သီးခြား request ပြုလုပ်ရပါမည်။",
            "accepted": "VPN key ထုတ်ပေးရန် request ကို လက်ခံပြီးပါပြီ။",
        },
    }

    def __init__(self, db, *, provisioning_service, data_limit_service=None):
        super().__init__(db)
        self.provisioning_service = provisioning_service
        self.data_limit_service = data_limit_service

    async def _provision_paid(self, request, *, actor_user_id: int):
        result = await self.provisioning_service.provision(request, actor_user_id=actor_user_id)
        if result.is_failure or self.data_limit_service is None:
            return result
        success = result.value
        limit_result = await self.data_limit_service.apply_for_key(
            key_id=success.vpn_key_id,
            actor_user_id=actor_user_id,
            operation_id=success.operation_id + ":limit",
        )
        return limit_result

    async def customer_paid_order(self, *, user_id: int, order_id: int, idempotency_key: str, request_reference: str, language: str = "en"):
        return await self._provision_paid(
            VPNProvisioningRequest(
                user_id=user_id,
                source_type=ProvisioningSource.PAID_ORDER,
                workload_type="paid",
                order_id=order_id,
                idempotency_key=idempotency_key,
                request_reference=request_reference,
            ),
            actor_user_id=user_id,
        )

    async def admin_paid_order(self, *, admin_user_id: int, customer_user_id: int, order_id: int, idempotency_key: str, request_reference: str, language: str = "en"):
        return await self._provision_paid(
            VPNProvisioningRequest(
                user_id=customer_user_id,
                source_type=ProvisioningSource.PAID_ORDER,
                workload_type="paid",
                order_id=order_id,
                idempotency_key=idempotency_key,
                request_reference=request_reference,
            ),
            actor_user_id=admin_user_id,
        )

    def payment_approved_notice(self, language: str = "en") -> str:
        return self.MESSAGES.get(language, self.MESSAGES["en"])["manual_required"]

    def accepted_notice(self, language: str = "en") -> str:
        return self.MESSAGES.get(language, self.MESSAGES["en"])["accepted"]
