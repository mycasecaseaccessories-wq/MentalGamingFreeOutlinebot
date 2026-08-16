from __future__ import annotations

from app.models.vpn_recovery import RecoveryStatus, RotationRequest, RenewalRequest


class VPNRecoveryService:
    """Phase 4.6 recovery service boundary.

    Provider-specific rotation/renewal orchestration is intentionally injected
    by callers; this class provides the stable registry contract and request
    validation boundary.
    """

    def __init__(self, db, provider=None):
        self.db = db
        self.provider = provider

    async def renew(self, request: RenewalRequest):
        request.validate()
        return {"status": RecoveryStatus.PENDING.value, "request": request}

    async def rotate(self, request: RotationRequest):
        request.validate()
        return {"status": RecoveryStatus.PENDING.value, "request": request}
