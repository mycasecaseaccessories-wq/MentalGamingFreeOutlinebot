"""
Service Registry — dependency container.

Ensures each service class is instantiated only once per application
lifetime.  Handlers and middleware look up services here instead of
creating new instances, preventing duplicate DB connections, redundant
caches, and inconsistent state.

Usage
-----
    from app.services.registry import ServiceRegistry

    # In Bootstrap.setup():
    registry = ServiceRegistry(db)
    registry.initialise_all()

    # Attach to bot_data so handlers can access services:
    application.bot_data["registry"] = registry

    # In any handler:
    registry = context.bot_data["registry"]
    user_service = registry.get(UserService)

Design
------
  • Services are keyed by their class type.
  • get() raises KeyError for unknown services (fails loudly, not silently).
  • initialise_all() creates every registered service in dependency order.

Phase 0.5: Core container for all Phase 0.x services.
Future:    Additional services (WalletService, VPNKeyService, …) added in
           Phase 1+ will be registered here.
"""

from __future__ import annotations

import logging
from typing import Any, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceRegistry:
    """
    Lightweight service container / dependency injector.

    Holds one instance of each service.  Services are created lazily
    on first get() call, or eagerly via initialise_all().
    """

    def __init__(self, db) -> None:
        """
        Args:
            db: Initialised DatabaseManager passed to all services.
        """
        self._db = db
        self._instances: dict[type, Any] = {}

    # ── Registration / lookup ─────────────────────────────────────────────

    def register(self, service_class: type, instance: Any) -> None:
        """
        Store an already-created service instance.

        Args:
            service_class: The class (used as lookup key).
            instance:      The service instance to store.
        """
        self._instances[service_class] = instance
        logger.debug("ServiceRegistry: registered %s", service_class.__name__)

    def get(self, service_class: Type[T]) -> T:
        """
        Return the registered instance of *service_class*.

        Args:
            service_class: The service class to look up.

        Returns:
            The registered service instance.

        Raises:
            KeyError: If *service_class* has not been registered.
        """
        instance = self._instances.get(service_class)
        if instance is None:
            raise KeyError(
                f"Service {service_class.__name__!r} is not registered. "
                f"Call initialise_all() or register() first."
            )
        return instance  # type: ignore[return-value]

    def get_or_none(self, service_class: Type[T]) -> T | None:
        """
        Return the registered instance or None (never raises).

        Use this when a service is optional (e.g. only registered in
        production, not in test environments).
        """
        return self._instances.get(service_class)  # type: ignore[return-value]

    def is_registered(self, service_class: type) -> bool:
        """Return True when *service_class* has a registered instance."""
        return service_class in self._instances

    # ── Bulk initialisation ───────────────────────────────────────────────

    def initialise_all(self) -> None:
        """
        Create and register all Phase 0.x services in dependency order.

        Services are created with the shared DatabaseManager so they all
        share the same connection pool.

        Dependency order:
          SettingsService → (independent)
          LanguageService → (independent)
          UserService     → (independent)
          PreferenceService → (independent)
          HealthService   → depends on db (injected post-init via set_db)
        """
        from app.services.settings_service import SettingsService
        from app.services.language_service import LanguageService
        from app.services.user_service import UserService
        from app.services.preference_service import PreferenceService
        from app.services.health_service import HealthService

        services_to_create = [
            SettingsService,
            LanguageService,
            UserService,
            PreferenceService,
        ]

        for service_class in services_to_create:
            if not self.is_registered(service_class):
                instance = service_class(self._db)
                self.register(service_class, instance)
                logger.info("  ✓ %s initialised", service_class.__name__)

        # HealthService needs additional dependencies set after bot init.
        if not self.is_registered(HealthService):
            from app.cache import cache as default_cache
            health = HealthService(db=self._db, cache=default_cache)
            self.register(HealthService, health)
            logger.info("  ✓ HealthService initialised")

        logger.info(
            "ServiceRegistry: %d services ready", len(self._instances)
        )

    def inject_bot(self, bot) -> None:
        """
        Pass the Telegram Bot instance to HealthService after bot init.

        Args:
            bot: telegram.Bot instance (available after application.initialize()).
        """
        from app.services.health_service import HealthService
        health = self.get_or_none(HealthService)
        if health is not None:
            health._bot = bot
            logger.debug("ServiceRegistry: bot injected into HealthService")

    def inject_scheduler(self, scheduler) -> None:
        """
        Pass the Scheduler instance to HealthService.

        Args:
            scheduler: Scheduler instance.
        """
        from app.services.health_service import HealthService
        health = self.get_or_none(HealthService)
        if health is not None:
            health._scheduler = scheduler
            logger.debug("ServiceRegistry: scheduler injected into HealthService")

    def list_registered(self) -> list[str]:
        """Return the names of all registered service classes."""
        return [cls.__name__ for cls in self._instances]
