"""Integration tests for ServiceRegistry (app.services.registry)."""

from __future__ import annotations

import pytest

from app.services.health_service import HealthService
from app.services.language_service import LanguageService
from app.services.preference_service import PreferenceService
from app.services.registry import ServiceRegistry
from app.services.settings_service import SettingsService
from app.services.user_service import UserService

pytestmark = pytest.mark.integration


class TestServiceRegistryResolution:
    def test_all_core_services_registered(self, service_registry: ServiceRegistry) -> None:
        """After initialise_all(), all Phase 0.x services must be registered."""
        for svc_class in [
            SettingsService,
            LanguageService,
            UserService,
            PreferenceService,
            HealthService,
        ]:
            assert service_registry.is_registered(svc_class), (
                f"{svc_class.__name__} was not registered"
            )

    def test_get_returns_same_instance(self, service_registry: ServiceRegistry) -> None:
        """get() must return the exact same singleton."""
        svc1 = service_registry.get(UserService)
        svc2 = service_registry.get(UserService)
        assert svc1 is svc2

    def test_get_unknown_service_raises(self, service_registry: ServiceRegistry) -> None:
        class UnknownService:
            pass

        with pytest.raises(KeyError, match="UnknownService"):
            service_registry.get(UnknownService)

    def test_get_or_none_returns_none_for_unknown(
        self, service_registry: ServiceRegistry
    ) -> None:
        class UnknownService:
            pass

        assert service_registry.get_or_none(UnknownService) is None

    def test_list_registered_returns_names(self, service_registry: ServiceRegistry) -> None:
        names = service_registry.list_registered()
        assert "UserService" in names
        assert "LanguageService" in names

    def test_resolve_with_factory(self, service_registry: ServiceRegistry) -> None:
        class DummyService:
            pass

        service_registry.register_factory(DummyService, lambda: DummyService())
        instance = service_registry.resolve(DummyService)
        assert isinstance(instance, DummyService)
