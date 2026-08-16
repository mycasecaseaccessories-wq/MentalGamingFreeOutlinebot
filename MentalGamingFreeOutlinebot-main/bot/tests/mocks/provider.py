"""Mock providers for VPN, payment, notification, and storage."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock


class MockVPNProvider:
    """Mock Outline VPN provider (Phase 4+)."""

    def __init__(self) -> None:
        self.create_key = AsyncMock(return_value={
            "id": "mock-key-1",
            "accessUrl": "ss://mock@192.0.2.1:1234/",
            "name": "TestUser",
        })
        self.delete_key = AsyncMock(return_value=True)
        self.get_key = AsyncMock(return_value={"id": "mock-key-1"})
        self.list_keys = AsyncMock(return_value=[])
        self.get_server_info = AsyncMock(return_value={"name": "Mock Server", "version": "1.0"})
        self.set_data_limit = AsyncMock(return_value=True)


class MockPaymentProvider:
    """Mock payment provider (Phase 3+)."""

    def __init__(self) -> None:
        self.create_invoice = AsyncMock(return_value={"invoice_id": "inv_mock_001", "url": "https://pay.example.com/inv_mock_001"})
        self.check_payment = AsyncMock(return_value={"status": "paid", "amount": "9.99"})
        self.refund = AsyncMock(return_value=True)


class MockNotificationProvider:
    """Mock notification provider."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.send = AsyncMock(side_effect=self._record_send)
        self.send_bulk = AsyncMock(return_value={"sent": 0, "failed": 0})

    async def _record_send(self, user_id: int, message: str, **kwargs: Any) -> bool:
        self.sent.append({"user_id": user_id, "message": message, **kwargs})
        return True


class MockStorageProvider:
    """Mock object storage provider."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self.upload = AsyncMock(side_effect=self._record_upload)
        self.download = AsyncMock(side_effect=self._record_download)
        self.delete = AsyncMock(return_value=True)
        self.exists = AsyncMock(side_effect=lambda key: key in self._objects)

    async def _record_upload(self, key: str, data: bytes, **_: Any) -> str:
        self._objects[key] = data
        return f"https://storage.example.com/{key}"

    async def _record_download(self, key: str) -> bytes | None:
        return self._objects.get(key)
