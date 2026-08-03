"""
PackageService — VPN subscription package catalogue.

Responsibilities (Phase 2+):
  • List available subscription packages (name, price, duration, data limit).
  • Create, update, and deactivate packages (admin).
  • Retrieve the active package for a given user.
"""

from __future__ import annotations

from .base import BaseService


class PackageService(BaseService):
    """Manages VPN subscription package definitions."""

    async def list_active(self) -> list:
        """
        Return all currently active packages.

        Returns:
            List of Package domain objects ordered by price ascending.
        """
        # TODO (Phase 2): call PackageRepository.list_active()
        raise NotImplementedError("PackageService.list_active — Phase 2")

    async def get_by_id(self, package_id: int) -> object | None:
        """Retrieve a single package by its primary key."""
        # TODO (Phase 2): call PackageRepository.get_by_id()
        raise NotImplementedError("PackageService.get_by_id — Phase 2")

    async def create(self, name: str, price: float, duration_days: int) -> object:
        """Create a new subscription package (admin)."""
        # TODO (Phase 2): validate inputs, call PackageRepository.create()
        raise NotImplementedError("PackageService.create — Phase 2")

    async def deactivate(self, package_id: int) -> None:
        """Soft-delete a package by marking it inactive."""
        # TODO (Phase 2): call PackageRepository.update(is_active=False)
        raise NotImplementedError("PackageService.deactivate — Phase 2")
