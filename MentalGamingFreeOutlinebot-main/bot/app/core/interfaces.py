"""
Shared abstract interfaces (contracts).

Future modules must depend on these interfaces rather than on concrete
implementations.  This keeps the architecture loosely coupled: swapping
a Redis cache for a memory cache, or an Outline VPN provider for a mock,
requires only a new class that implements the interface.

Interfaces defined here
-----------------------
CacheProvider        — get / set / delete / clear / exists.
NotificationProvider — send a notification to a user.
VPNProvider          — create / revoke / sync VPN keys.
PaymentProvider      — initiate / verify payments.
StorageProvider      — put / get / delete opaque objects.
AuthenticationProvider — authenticate and revoke identities.

Phase 0.6: Interface definitions only.  Concrete implementations in Phase 3+.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Cache provider
# ---------------------------------------------------------------------------

class CacheProvider(ABC):
    """
    Abstract cache backend.

    Concrete implementations: MemoryCache (Phase 0.5), RedisCache (future).
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Return the value for *key*, or None if missing/expired."""

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        *,
        tags: Iterable[str] = (),
    ) -> None:
        """Store *value* under *key* with optional TTL and invalidation tags."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Remove *key*. Return True if it existed."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if *key* exists and has not expired."""

    @abstractmethod
    async def clear(self, prefix: Optional[str] = None) -> int:
        """Remove all keys (or those with *prefix*). Return count removed."""

    @abstractmethod
    async def invalidate_tags(self, *tags: str) -> int:
        """Remove entries carrying any of *tags*. Return count removed."""


# ---------------------------------------------------------------------------
# Notification provider
# ---------------------------------------------------------------------------

class NotificationProvider(ABC):
    """
    Abstract notification delivery backend.

    Concrete implementations:
        TelegramNotifier — sends messages via python-telegram-bot (Phase 1).
        LogNotifier      — writes to logger (useful in tests).
    """

    @abstractmethod
    async def send(
        self,
        user_id: int,
        message: str,
        *,
        notification_type: str = "system",
        parse_html: bool = True,
    ) -> bool:
        """
        Send *message* to *user_id*.

        Args:
            user_id:           Telegram user ID.
            message:           Message text (HTML allowed when parse_html=True).
            notification_type: Category from NotificationType enum values.
            parse_html:        Whether to use HTML parse mode.

        Returns:
            True if the message was delivered successfully.
        """

    @abstractmethod
    async def broadcast(
        self,
        user_ids: list[int],
        message: str,
        *,
        notification_type: str = "broadcast",
    ) -> dict[int, bool]:
        """
        Send *message* to multiple users.

        Returns:
            Mapping of user_id → delivery success.
        """


# ---------------------------------------------------------------------------
# VPN provider
# ---------------------------------------------------------------------------

class VPNProvider(ABC):
    """
    Abstract VPN key management backend.

    Concrete implementation: OutlineVPNProvider (Phase 4).
    """

    @abstractmethod
    async def create_key(
        self,
        server_id: int,
        name: str,
        *,
        data_limit_gb: float = 0.0,
    ) -> dict[str, Any]:
        """
        Create a new access key on *server_id*.

        Returns:
            Dict with at least: {"key_id": str, "access_url": str}.
        """

    @abstractmethod
    async def revoke_key(self, server_id: int, key_id: str) -> bool:
        """
        Revoke (delete) an access key.

        Returns:
            True if the key was found and removed.
        """

    @abstractmethod
    async def update_data_limit(
        self, server_id: int, key_id: str, limit_gb: float
    ) -> bool:
        """Set the data-transfer limit for a key. 0 = unlimited."""

    @abstractmethod
    async def get_usage(self, server_id: int) -> dict[str, int]:
        """
        Return current data usage per key on *server_id*.

        Returns:
            Dict mapping key_id → bytes transferred.
        """

    @abstractmethod
    async def ping(self, server_id: int) -> bool:
        """Return True if the server API is reachable."""


# ---------------------------------------------------------------------------
# Payment provider
# ---------------------------------------------------------------------------

class PaymentProvider(ABC):
    """
    Abstract payment processing backend.

    Concrete implementations: WalletPayment (Phase 3), ManualPayment (Phase 3),
    USDTPayment (Phase 3+), StripePayment (future).
    """

    @abstractmethod
    async def initiate(
        self,
        order_id: int,
        amount: float,
        currency: str,
        *,
        user_id: int,
        description: str = "",
    ) -> dict[str, Any]:
        """
        Start a payment flow for *order_id*.

        Returns:
            Dict with at least: {"reference": str, "instructions": str}.
        """

    @abstractmethod
    async def verify(self, reference: str) -> bool:
        """Return True if payment with *reference* has been confirmed."""

    @abstractmethod
    async def refund(self, reference: str, amount: float) -> bool:
        """Initiate a refund. Return True if successful."""


# ---------------------------------------------------------------------------
# Cross-channel provider contracts
# ---------------------------------------------------------------------------

class StorageProvider(ABC):
    """Opaque object storage contract for local or hosted backends."""

    @abstractmethod
    async def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        """Store bytes and return a stable object identifier."""

    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]:
        """Return object bytes, or None when the object is absent."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an object and return whether it existed."""


class AuthenticationProvider(ABC):
    """Identity provider contract independent of Telegram or a web framework."""

    @abstractmethod
    async def authenticate(self, credential: str) -> Optional[dict[str, Any]]:
        """Resolve a credential to an identity payload."""

    @abstractmethod
    async def revoke(self, identity: str) -> bool:
        """Revoke an identity/session and return whether it was found."""
