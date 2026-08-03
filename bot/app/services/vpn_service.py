"""
VPNService — VPN key provisioning and access control.

Responsibilities (Phase 4+):
  • Issue a new Outline access key for a subscriber.
  • Revoke a key on subscription expiry or admin action.
  • Apply bandwidth limits to a key.
  • Query the current status of a key.
"""

from __future__ import annotations

from .base import BaseService


class VPNService(BaseService):
    """Manages VPN key lifecycle via the Outline API."""

    async def issue_key(self, telegram_id: int, server_id: int, name: str = "") -> object:
        """
        Create and return a new Outline access key for the user.

        Args:
            telegram_id: The user receiving the key.
            server_id:   Target Outline server.
            name:        Optional display name for the key in the Outline manager.

        Returns:
            VPNKey domain object containing the access URL.
        """
        # TODO (Phase 4): call Outline API, persist key record, notify user
        raise NotImplementedError("VPNService.issue_key — Phase 4")

    async def revoke_key(self, key_id: int) -> None:
        """
        Delete a key from the Outline server and mark it as revoked.

        Args:
            key_id: Primary key of the VPNKey record in the local database.
        """
        # TODO (Phase 4): call Outline API DELETE /access-keys/{id}
        raise NotImplementedError("VPNService.revoke_key — Phase 4")

    async def set_data_limit(self, key_id: int, limit_bytes: int) -> None:
        """
        Apply a monthly data cap to the given key.

        Args:
            limit_bytes: Monthly data limit in bytes.  0 = unlimited.
        """
        # TODO (Phase 4): call Outline API PUT /access-keys/{id}/data-limit
        raise NotImplementedError("VPNService.set_data_limit — Phase 4")

    async def get_key_status(self, key_id: int) -> object:
        """
        Return the current status and usage of a VPN key.

        Returns:
            VPNKeyStatus with is_active, bytes_used, limit_bytes fields.
        """
        # TODO (Phase 4): query Outline metrics API
        raise NotImplementedError("VPNService.get_key_status — Phase 4")
