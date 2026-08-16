from __future__ import annotations

from app.models.vpn_recovery import RecoveryStatus


class VPNReconciliationService:
    """Phase 4.6 local/remote state reconciliation boundary."""

    def __init__(self, db, provider=None):
        self.db = db
        self.provider = provider

    async def reconcile(self, *, key_id: int | None = None):
        if key_id is not None and key_id <= 0:
            raise ValueError("key_id must be positive")
        return {"status": RecoveryStatus.RECONCILIATION_REQUIRED.value, "key_id": key_id}
