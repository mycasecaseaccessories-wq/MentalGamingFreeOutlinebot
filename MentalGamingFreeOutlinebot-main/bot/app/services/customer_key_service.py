"""Phase 1.5 read-only customer VPN key service.

Security:
- Every lookup starts from Telegram identity and resolves the internal user id.
- Key details/access URLs are fetched with an owner-scoped repository query.
- The service never logs or emits the full access URL.
- No Outline API, wallet, payment, renewal, revoke, or delete operation occurs.
"""

from __future__ import annotations

from app.models.customer_keys import (
    ConnectionInfo,
    CustomerKeyDetail,
    CustomerKeyPage,
    CustomerKeySummary,
    KeyUsage,
)
from app.models.enums import VPNKeyStatus
from app.services.base import BaseService
from database.repositories.package_repository import PackageRepository
from database.repositories.server_repository import ServerRepository
from database.repositories.user_repository import UserRepository
from database.repositories.vpn_key_repository import VPNKeyRepository


class CustomerKeyService(BaseService):
    """Owner-scoped, read-only VPN key queries for customers."""

    async def _resolve_user_id(self, telegram_id: int) -> int:
        if telegram_id <= 0:
            raise ValueError("telegram_id must be positive")
        async with self.db.session() as session:
            user = await UserRepository(session).get_by_telegram_id(telegram_id)
            if user is None:
                raise LookupError("User not found")
            return int(user.id)

    @staticmethod
    def _remaining(limit_bytes: int | None, used_bytes: int | None) -> int | None:
        if limit_bytes is None:
            return None
        return max(int(limit_bytes) - max(int(used_bytes or 0), 0), 0)

    @staticmethod
    def _percentage(limit_bytes: int | None, used_bytes: int | None) -> float | None:
        if not limit_bytes or int(limit_bytes) <= 0:
            return None
        value = max(int(used_bytes or 0), 0) / int(limit_bytes) * 100
        return round(min(value, 100.0), 1)

    async def list_customer_keys(
        self,
        telegram_id: int,
        *,
        page: int = 1,
        page_size: int = 5,
    ) -> CustomerKeyPage:
        page = max(1, int(page))
        page_size = min(10, max(1, int(page_size)))
        user_id = await self._resolve_user_id(telegram_id)

        async with self.db.session() as session:
            keys = VPNKeyRepository(session)
            packages = PackageRepository(session)
            servers = ServerRepository(session)

            total = await keys.count_by_user(user_id)
            rows = await keys.list_by_user(
                user_id,
                limit=page_size,
                offset=(page - 1) * page_size,
            )

            package_ids = {row.package_id for row in rows if row.package_id}
            server_ids = {row.server_id for row in rows if row.server_id}
            package_map = {}
            server_map = {}

            for package_id in package_ids:
                pkg = await packages.get_by_id(int(package_id))
                if pkg is not None:
                    package_map[int(package_id)] = pkg

            for server_id in server_ids:
                srv = await servers.get_by_id(int(server_id))
                if srv is not None:
                    server_map[int(server_id)] = srv

            items = tuple(
                CustomerKeySummary(
                    key_id=row.id,
                    key_type=row.key_type or "paid",
                    status=row.status or ("active" if row.is_active else "revoked"),
                    package_name=(
                        package_map.get(row.package_id).name
                        if row.package_id in package_map
                        else row.name
                    ),
                    server_name=(
                        server_map.get(row.server_id).name
                        if row.server_id in server_map
                        else None
                    ),
                    country=(
                        server_map.get(row.server_id).country_code
                        if row.server_id in server_map
                        else None
                    ),
                    data_limit_bytes=row.data_limit_bytes,
                    used_bytes=max(int(row.used_bytes or 0), 0),
                    remaining_bytes=self._remaining(row.data_limit_bytes, row.used_bytes),
                    expires_at=row.expires_at,
                )
                for row in rows
            )

        return CustomerKeyPage(
            items=items,
            page=page,
            page_size=page_size,
            has_previous=page > 1,
            has_next=(page * page_size) < total,
            total=total,
        )

    async def get_customer_key(
        self,
        telegram_id: int,
        key_id: int,
    ) -> CustomerKeyDetail | None:
        if key_id <= 0:
            return None
        user_id = await self._resolve_user_id(telegram_id)

        async with self.db.session() as session:
            row = await VPNKeyRepository(session).get_owned(key_id, user_id)
            if row is None:
                return None

            pkg = (
                await PackageRepository(session).get_by_id(row.package_id)
                if row.package_id
                else None
            )
            server = await ServerRepository(session).get_by_id(row.server_id)

            return CustomerKeyDetail(
                key_id=row.id,
                key_type=row.key_type or "paid",
                status=row.status or ("active" if row.is_active else "revoked"),
                name=row.name,
                package_name=(pkg.name if pkg is not None else row.name),
                server_name=(server.name if server is not None else None),
                country=(server.country_code if server is not None else None),
                data_limit_bytes=row.data_limit_bytes,
                used_bytes=max(int(row.used_bytes or 0), 0),
                remaining_bytes=self._remaining(row.data_limit_bytes, row.used_bytes),
                device_limit=row.device_limit,
                created_at=row.created_at,
                expires_at=row.expires_at,
                last_synced_at=row.last_synced_at,
            )

    async def get_usage_summary(
        self,
        telegram_id: int,
        key_id: int,
    ) -> KeyUsage | None:
        detail = await self.get_customer_key(telegram_id, key_id)
        if detail is None:
            return None
        return KeyUsage(
            key_id=detail.key_id,
            data_limit_bytes=detail.data_limit_bytes,
            used_bytes=detail.used_bytes,
            remaining_bytes=detail.remaining_bytes,
            percentage=self._percentage(detail.data_limit_bytes, detail.used_bytes),
            last_synced_at=detail.last_synced_at,
            expires_at=detail.expires_at,
        )

    async def get_connection_info(
        self,
        telegram_id: int,
        key_id: int,
    ) -> ConnectionInfo | None:
        user_id = await self._resolve_user_id(telegram_id)
        async with self.db.session() as session:
            row = await VPNKeyRepository(session).get_owned(key_id, user_id)
            if row is None:
                return None

            status = row.status or ("active" if row.is_active else "revoked")
            if status != VPNKeyStatus.ACTIVE.value or not row.is_active:
                return None

            server = await ServerRepository(session).get_by_id(row.server_id)
            return ConnectionInfo(
                key_id=row.id,
                access_url=row.access_url,
                server_name=(server.name if server is not None else None),
                country=(server.country_code if server is not None else None),
                status=status,
            )

    async def can_connect(self, telegram_id: int, key_id: int) -> bool:
        return await self.get_connection_info(telegram_id, key_id) is not None

    async def can_renew(self, telegram_id: int, key_id: int) -> bool:
        detail = await self.get_customer_key(telegram_id, key_id)
        if detail is None:
            return False
        if detail.key_type == "free_trial":
            return False
        return detail.status in {"active", "expired", "suspended"}
