"""Performance benchmarks for core platform components."""

from __future__ import annotations

import time

import pytest

from app.core.result import Failure, Success
from app.core.security import generate_token, hash_value
from tests.factories.user_factory import UserFactory
from tests.performance.benchmarks import timed

pytestmark = pytest.mark.performance


class TestResultPatternPerformance:
    def test_success_creation_is_fast(self) -> None:
        with timed("Success(x) × 10,000", max_ms=200):
            for i in range(10_000):
                _ = Success(i)

    def test_failure_creation_is_fast(self) -> None:
        with timed("Failure() × 10,000", max_ms=200):
            for i in range(10_000):
                _ = Failure("code", f"message {i}")

    def test_map_chain_is_fast(self) -> None:
        with timed("Success.map chain × 1,000", max_ms=50):
            for _ in range(1_000):
                _ = Success(1).map(lambda x: x + 1).map(lambda x: x * 2)


class TestSecurityPerformance:
    def test_token_generation_is_fast(self) -> None:
        with timed("generate_token() × 1,000", max_ms=500):
            for _ in range(1_000):
                _ = generate_token(32)

    def test_hash_value_is_fast(self) -> None:
        with timed("hash_value() × 1,000", max_ms=500):
            for _ in range(1_000):
                _ = hash_value("password", "salt")


class TestFactoryPerformance:
    def test_user_factory_batch_is_fast(self) -> None:
        with timed("UserFactory.build_batch(1000)", max_ms=2000):
            users = UserFactory.build_batch(1_000)
        assert len(users) == 1_000

    def test_all_users_have_unique_ids(self) -> None:
        UserFactory.reset()
        users = UserFactory.build_batch(500)
        ids = [u.telegram_id for u in users]
        assert len(set(ids)) == 500
