"""Unit tests for VersionManager (app.core.versioning)."""

from __future__ import annotations

import pytest

from app.core.versioning import VersionManager

pytestmark = pytest.mark.unit


class TestVersionManager:
    def test_current_version(self) -> None:
        vm = VersionManager(current="0.7.0", migration="0004", build="test")
        assert vm.current == "0.7.0"

    def test_migration_version(self) -> None:
        vm = VersionManager(current="0.7.0", migration="0004", build="test")
        assert vm.migration == "0004"

    def test_build_info(self) -> None:
        vm = VersionManager(current="0.7.0", migration="0004", build="ci-42")
        assert vm.build == "ci-42"

    def test_compatibility_exact_match(self) -> None:
        vm = VersionManager(current="0.7.0", migration="0004", build="x")
        compat = vm.compatibility(["0.7.0"])
        assert compat["0.7.0"] is True

    def test_compatibility_older_patch(self) -> None:
        vm = VersionManager(current="0.7.0", migration="0004", build="x")
        compat = vm.compatibility(["0.6.1"])
        assert compat["0.6.1"] is True

    def test_compatibility_newer_version_false(self) -> None:
        vm = VersionManager(current="0.7.0", migration="0004", build="x")
        compat = vm.compatibility(["0.8.0"])
        assert compat["0.8.0"] is False

    def test_compatibility_multiple(self) -> None:
        vm = VersionManager(current="0.6.1", migration="0004", build="test")
        result = vm.compatibility(["0.6.0", "0.6.1", "0.7.0"])
        assert result == {"0.6.0": True, "0.6.1": True, "0.7.0": False}
