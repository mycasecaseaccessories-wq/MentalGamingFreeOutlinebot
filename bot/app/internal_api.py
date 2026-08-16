"""Transport-neutral internal API facade.

Adapters such as Telegram, Mini App, Web Dashboard, REST, or GraphQL can receive
the same registered application services through this facade. It intentionally
contains no HTTP or Telegram implementation.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class ServiceResolver(Protocol):
    def resolve(self, service: type[T]) -> T:
        ...


class InternalAPI:
    def __init__(self, services: ServiceResolver) -> None:
        self._services = services

    def resolve(self, service: type[T]) -> T:
        """Resolve an application service from the shared service registry."""
        return self._services.resolve(service)
