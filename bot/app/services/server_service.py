"""
ServerService — Outline VPN server lifecycle management.

Responsibilities (Phase 4+):
  • Register and deregister Outline server instances.
  • Health-check registered servers.
  • Select the optimal server for a new key (load balancing).
  • Report per-server usage statistics.
"""

from __future__ import annotations

from .base import BaseService


class ServerService(BaseService):
    """Manages the fleet of Outline VPN servers."""

    async def list_servers(self) -> list:
        """Return all registered server records."""
        # TODO (Phase 4): call ServerRepository.list_all()
        raise NotImplementedError("ServerService.list_servers — Phase 4")

    async def add_server(self, api_url: str, cert_sha256: str, name: str) -> object:
        """
        Register a new Outline server.

        Args:
            api_url:      The Outline management API URL (from the server config).
            cert_sha256:  SHA-256 fingerprint of the server TLS certificate.
            name:         Human-readable label for the server.
        """
        # TODO (Phase 4): validate reachability, call ServerRepository.create()
        raise NotImplementedError("ServerService.add_server — Phase 4")

    async def remove_server(self, server_id: int) -> None:
        """Deregister a server (admin). Revokes all associated keys first."""
        # TODO (Phase 4): revoke keys, call ServerRepository.delete()
        raise NotImplementedError("ServerService.remove_server — Phase 4")

    async def health_check(self, server_id: int) -> bool:
        """
        Ping the Outline management API to verify the server is reachable.

        Returns:
            True if the server responded successfully.
        """
        # TODO (Phase 4): call Outline REST API /server endpoint
        raise NotImplementedError("ServerService.health_check — Phase 4")

    async def pick_server(self) -> object:
        """
        Select the best server for issuing a new key.

        Strategy (Phase 4): round-robin with health-check fallback.
        """
        # TODO (Phase 4): implement load-balancing strategy
        raise NotImplementedError("ServerService.pick_server — Phase 4")
