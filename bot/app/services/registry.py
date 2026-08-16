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
import inspect
from typing import Any, Callable, Type, TypeVar

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
        self._factories: dict[type, Callable[..., Any]] = {}

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

    def register_factory(
        self,
        service_class: type[T],
        factory: Callable[..., T],
    ) -> None:
        """Register a lazy factory for automatic dependency resolution."""
        self._factories[service_class] = factory

    def resolve(self, service_class: type[T]) -> T:
        """Resolve a service lazily, injecting registered dependencies.

        A factory takes precedence. For ordinary classes, constructor
        annotations are inspected and resolved from this registry. The shared
        database manager is injected for the existing service constructors.
        """
        existing = self.get_or_none(service_class)
        if existing is not None:
            return existing

        factory = self._factories.get(service_class)
        if factory is not None:
            instance = factory()
        else:
            signature = inspect.signature(service_class)
            kwargs: dict[str, Any] = {}
            for name, parameter in signature.parameters.items():
                if name == "db":
                    kwargs[name] = self._db
                elif parameter.annotation is not inspect.Parameter.empty:
                    dependency = self.get_or_none(parameter.annotation)
                    if dependency is not None:
                        kwargs[name] = dependency
            instance = service_class(**kwargs)
        self.register(service_class, instance)
        return instance

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
        from app.services.customer_entry_service import CustomerEntryService
        from app.services.customer_navigation_service import CustomerNavigationService
        from app.services.health_service import HealthService
        from app.services.profile_service import ProfileService
        from app.services.wallet_service import WalletService
        from app.services.wallet_payment_service import WalletPaymentService
        from app.services.manual_payment_service import ManualPaymentService
        from app.services.payment_submission_service import PaymentSubmissionService
        from app.services.payment_review_service import PaymentReviewService
        from app.services.history_service import HistoryService
        from app.services.server_service import ServerService
        from app.services.server_selection_service import ServerSelectionService
        from app.services.server_reservation_service import ServerReservationService
        from app.services.vpn_provisioning_service import VPNProvisioningService
        from app.services.vpn_data_limit_service import VPNDataLimitService
        from app.services.vpn_recovery_service import VPNRecoveryService
        from app.services.vpn_reconciliation_service import VPNReconciliationService
        from app.services.vpn_lifecycle_service import VPNLifecycleService
        from app.core.providers import providers
        from app.integrations.outline_provider import OutlineProvider
        from app.services.outline_setup_service import OutlineSetupService
        from app.services.ssh_discovery_service import SSHDiscoveryService
        from app.services.outline_provisioning_service import OutlineProvisioningService
        from app.services.outline_server_sync_service import OutlineServerSyncService
        from app.services.support_service import SupportService
        from app.services.package_catalog_service import PackageCatalogService
        from app.services.customer_key_service import CustomerKeyService
        from app.services.order_service import OrderService
        from app.services.checkout_service import CheckoutService
        from app.services.vpn_provisioning_entry_service import VPNProvisioningEntryService
        from app.services.free_trial_claim_service import FreeTrialClaimService
        from app.services.trial_server_routing_service import TrialServerRoutingService
        from app.services.free_trial_provisioning_service import FreeTrialProvisioningService
        from app.services.free_trial_abuse_service import FreeTrialAbuseProtectionService
        from app.services.free_trial_analytics_service import FreeTrialAnalyticsService
        from app.services.free_trial_upgrade_service import FreeTrialUpgradeService

        services_to_create = [
            SettingsService,
            LanguageService,
            UserService,
            PreferenceService,
        ]

        for service_class in services_to_create:
            if not self.is_registered(service_class):
                instance = self.resolve(service_class)
                logger.info("  ✓ %s initialised", service_class.__name__)

        if not self.is_registered(FreeTrialAbuseProtectionService):
            self.register(FreeTrialAbuseProtectionService, FreeTrialAbuseProtectionService(db=self._db))
            logger.info("  ✓ FreeTrialAbuseProtectionService initialised")

        if not self.is_registered(FreeTrialClaimService):
            self.register(FreeTrialClaimService, FreeTrialClaimService(db=self._db, settings_service=self.get(SettingsService), abuse_service=self.get(FreeTrialAbuseProtectionService)))
            logger.info("  ✓ FreeTrialClaimService initialised")


        if not self.is_registered(CustomerEntryService):
            entry_service = CustomerEntryService(
                db=self._db,
                user_service=self.get(UserService),
                preference_service=self.get(PreferenceService),
            )
            self.register(CustomerEntryService, entry_service)
            logger.info("  ✓ CustomerEntryService initialised")

        if not self.is_registered(CustomerNavigationService):
            navigation_service = CustomerNavigationService(
                db=self._db,
                preference_service=self.get(PreferenceService),
            )
            self.register(CustomerNavigationService, navigation_service)
            logger.info("  ✓ CustomerNavigationService initialised")

        if not self.is_registered(ProfileService):
            self.register(ProfileService, ProfileService(
                db=self._db,
                user_service=self.get(UserService),
                preference_service=self.get(PreferenceService),
            ))
            logger.info("  ✓ ProfileService initialised")

        if not self.is_registered(WalletService):
            self.register(WalletService, WalletService(db=self._db))
            logger.info("  ✓ WalletService initialised")

        if not self.is_registered(WalletPaymentService):
            self.register(WalletPaymentService, WalletPaymentService(db=self._db))
            logger.info("  ✓ WalletPaymentService initialised")

        if not self.is_registered(ManualPaymentService):
            self.register(
                ManualPaymentService,
                ManualPaymentService(
                    db=self._db,
                    settings_service=self.get(SettingsService),
                ),
            )
            logger.info("  ✓ ManualPaymentService initialised")

        if not self.is_registered(PaymentSubmissionService):
            self.register(
                PaymentSubmissionService,
                PaymentSubmissionService(
                    db=self._db,
                    manual_payment_service=self.get(ManualPaymentService),
                ),
            )
            logger.info("  ✓ PaymentSubmissionService initialised")

        if not self.is_registered(PaymentReviewService):
            self.register(
                PaymentReviewService,
                PaymentReviewService(
                    db=self._db,
                    manual_payment_service=self.get(ManualPaymentService),
                ),
            )
            logger.info("  ✓ PaymentReviewService initialised")

        if not self.is_registered(HistoryService):
            self.register(HistoryService, HistoryService(db=self._db))
            logger.info("  ✓ HistoryService initialised")

        if not self.is_registered(ServerService):
            self.register(ServerService, ServerService(db=self._db))
            logger.info("  ✓ ServerService initialised")
        if not self.is_registered(ServerSelectionService):
            self.register(ServerSelectionService, ServerSelectionService(db=self._db))
            logger.info("  ✓ ServerSelectionService initialised")

        if not self.is_registered(TrialServerRoutingService):
            self.register(
                TrialServerRoutingService,
                TrialServerRoutingService(
                    db=self._db,
                    selection_service=self.get(ServerSelectionService),
                ),
            )
            logger.info("  ✓ TrialServerRoutingService initialised")
        if not self.is_registered(ServerReservationService):
            self.register(ServerReservationService, ServerReservationService(db=self._db))
            logger.info("  ✓ ServerReservationService initialised")
            outline_provider = providers.get_or_none("vpn", "outline") or providers.register("vpn", OutlineProvider(), name="outline", default=True)
            if not self.is_registered(VPNProvisioningService):
                self.register(VPNProvisioningService, VPNProvisioningService(db=self._db, selection_service=self.get(ServerSelectionService), reservation_service=self.get(ServerReservationService), provider_registry=providers, provider=outline_provider))
                logger.info("  ✓ VPNProvisioningService initialised")
        outline_provider = providers.get_or_none("vpn", "outline")
        if outline_provider is None:
            outline_provider = providers.register("vpn", OutlineProvider(), name="outline", default=True)

        if not self.is_registered(OutlineSetupService):
            self.register(OutlineSetupService, OutlineSetupService(db=self._db))
            logger.info("  ✓ OutlineSetupService initialised")

        if not self.is_registered(SSHDiscoveryService):
            self.register(SSHDiscoveryService, SSHDiscoveryService(db=self._db, outline_setup=self.get(OutlineSetupService)))
            logger.info("  ✓ SSHDiscoveryService initialised")

        if not self.is_registered(OutlineProvisioningService):
            ssh_discovery = self.get(SSHDiscoveryService)
            self.register(OutlineProvisioningService, OutlineProvisioningService(outline_setup=self.get(OutlineSetupService), ssh=ssh_discovery.provider))
            logger.info("  ✓ OutlineProvisioningService initialised")
            if not self.is_registered(OutlineServerSyncService):
                self.register(OutlineServerSyncService, OutlineServerSyncService(db=self._db))
                logger.info("  ✓ OutlineServerSyncService initialised")

        if not self.is_registered(VPNDataLimitService):
            self.register(VPNDataLimitService, VPNDataLimitService(db=self._db, provider=outline_provider))
            logger.info("  ✓ VPNDataLimitService initialised")
        if not self.is_registered(VPNLifecycleService):
            self.register(VPNLifecycleService, VPNLifecycleService(db=self._db, provider=outline_provider))
            logger.info("  ✓ VPNLifecycleService initialised")

        if not self.is_registered(VPNRecoveryService):
            self.register(VPNRecoveryService, VPNRecoveryService(db=self._db, provider=outline_provider))
        if not self.is_registered(VPNReconciliationService):
            self.register(VPNReconciliationService, VPNReconciliationService(db=self._db, provider=outline_provider))

        if not self.is_registered(SupportService):
            self.register(SupportService, SupportService(
                db=self._db,
                settings_service=self.get(SettingsService),
            ))
            logger.info("  ✓ SupportService initialised")

        if not self.is_registered(PackageCatalogService):
            self.register(PackageCatalogService, PackageCatalogService(db=self._db))
            logger.info("  ✓ PackageCatalogService initialised")

        if not self.is_registered(VPNProvisioningService):
            self.register(VPNProvisioningService, VPNProvisioningService(db=self._db, selection_service=self.get(ServerSelectionService), reservation_service=self.get(ServerReservationService), provider_registry=providers, provider=outline_provider))
            logger.info("  ✓ VPNProvisioningService initialised")

        if not self.is_registered(VPNProvisioningEntryService):
            self.register(VPNProvisioningEntryService, VPNProvisioningEntryService(db=self._db, provisioning_service=self.get(VPNProvisioningService), data_limit_service=self.get(VPNDataLimitService)))
            logger.info("  ✓ VPNProvisioningEntryService initialised")

        if not self.is_registered(FreeTrialProvisioningService):
            self.register(
                FreeTrialProvisioningService,
                FreeTrialProvisioningService(
                    db=self._db,
                    provisioning_service=self.get(VPNProvisioningService),
                    lifecycle_service=self.get(VPNLifecycleService),
                    data_limit_service=self.get(VPNDataLimitService),
                ),
            )
            logger.info("  ✓ FreeTrialProvisioningService initialised")

        if not self.is_registered(FreeTrialAnalyticsService):
            self.register(FreeTrialAnalyticsService, FreeTrialAnalyticsService(db=self._db))
            logger.info("  ✓ FreeTrialAnalyticsService initialised")

        if not self.is_registered(FreeTrialUpgradeService):
            self.register(
                FreeTrialUpgradeService,
                FreeTrialUpgradeService(
                    db=self._db,
                    data_limit_service=self.get(VPNDataLimitService),
                    lifecycle_service=self.get(VPNLifecycleService),
                    settings_service=self.get(SettingsService),
                    abuse_service=self.get(FreeTrialAbuseProtectionService),
                ),
            )
            logger.info("  ✓ FreeTrialUpgradeService initialised")

        if not self.is_registered(CustomerKeyService):
            self.register(CustomerKeyService, CustomerKeyService(db=self._db))
            logger.info("  ✓ CustomerKeyService initialised")

        if not self.is_registered(OrderService):
            self.register(OrderService, OrderService(db=self._db))
            logger.info("  ✓ OrderService initialised")

        if not self.is_registered(CheckoutService):
            self.register(CheckoutService, CheckoutService(db=self._db))
            logger.info("  ✓ CheckoutService initialised")

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
