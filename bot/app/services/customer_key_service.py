"""Owner-scoped, read-only VPN key service for Phase 1.5."""

from __future__ import annotations

from app.models.customer_keys import CustomerKeyDetail, CustomerKeySummary
from app.services.base import BaseService
from database.repositories.user_repository import UserRepository
from database.repositories.vpn_key_repository import VPNKeyRepository


class CustomerKeyService(BaseService):
    async def list_owned(self, telegram_id: int) -> tuple[CustomerKeySummary, ...]:
        async with self.db.session() as session:
            user = await UserRepository(session).get_by_telegram_id(telegram_id)
            if user is None:
                return ()
            rows = await VPNKeyRepository(session).list_owned(user.id)
            return tuple(self._summary(row) for row in rows)

    async def get_owned(self, telegram_id: int, key_id: int) -> CustomerKeyDetail | None:
        async with self.db.session() as session:
            user = await UserRepository(session).get_by_telegram_id(telegram_id)
            if user is None:
                return None
            row = await VPNKeyRepository(session).get_owned(key_id, user.id)
            return self._detail(row) if row else None

    @staticmethod
    def _summary(row) -> CustomerKeySummary:
        status = getattr(row, "status", None) or ("active" if row.is_active else "revoked")
        limit = getattr(row, "data_limit_bytes", None)
        used = getattr(row, "used_bytes", 0) or 0
        return CustomerKeySummary(
            key_id=row.id, key_type=getattr(row, "key_type", "paid"), status=status,
            package_name=None, server_name=None, country=None,
            data_limit_bytes=limit, used_bytes=used,
            remaining_bytes=max(limit - used, 0) if limit is not None else None,
            expires_at=row.expires_at,
        )

    @classmethod
    def _detail(cls, row) -> CustomerKeyDetail:
        summary = cls._summary(row)
        return CustomerKeyDetail(
            key_id=summary.key_id, key_type=summary.key_type, status=summary.status,
            package_name=summary.package_name, server_name=summary.server_name,
            country=summary.country, data_limit_bytes=summary.data_limit_bytes,
            used_bytes=summary.used_bytes, remaining_bytes=summary.remaining_bytes,
            expires_at=summary.expires_at, name=row.name,
            device_limit=getattr(row, "device_limit", None),
            created_at=row.created_at, last_synced_at=getattr(row, "last_synced_at", None),
        )