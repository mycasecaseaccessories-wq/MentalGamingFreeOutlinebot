"""Regression tests for Phase 0.6 shared foundation components."""

from __future__ import annotations

import pytest

from app.cache import CacheService, MemoryCache
from app.core.exceptions import ValidationException
from app.core.pagination import PaginationMeta, PaginationParams
from app.core.response import StandardResponse
from app.core.schemas import UserDTO
from app.models.enums import UserRole, UserStatus
from app.observability import RequestContext


@pytest.mark.asyncio
async def test_cache_tags_are_invalidated_with_namespace() -> None:
    backend = MemoryCache(prune_every=0)
    tenant_a = CacheService(backend, namespace="tenant-a")
    tenant_b = CacheService(backend, namespace="tenant-b")

    await tenant_a.set("user:1", "A", tags=("user:1",))
    await tenant_b.set("user:1", "B", tags=("user:1",))

    assert await tenant_a.invalidate_tags("user:1") == 1
    assert await tenant_a.get("user:1") is None
    assert await tenant_b.get("user:1") == "B"


def test_pagination_and_response_contracts() -> None:
    params = PaginationParams(page=3, page_size=20, search="outline")
    assert params.offset == 40

    meta = PaginationMeta(page=3, page_size=20, total=41)
    assert meta.total_pages == 3
    assert not meta.has_next
    assert meta.has_previous

    response = StandardResponse.ok({"count": 1}, request_id="req-1")
    assert response.success
    assert response.request_id == "req-1"


def test_dto_and_request_context_fields() -> None:
    user = UserDTO(
        telegram_id=42,
        full_name="Alice",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    assert user.role is UserRole.ADMIN

    context = RequestContext(current_user=user, current_role=user.role.value)
    assert context.current_user is user
    assert context.current_role == "admin"
    assert context.timestamp.tzinfo is not None
    assert context.as_log_extra()["role"] == "admin"


def test_app_exception_is_converted_to_standard_response() -> None:
    error = ValidationException("price", "must be positive", 0)
    response = StandardResponse.from_exception(error, request_id="req-2")

    assert not response.success
    assert response.errors[0].code == "validation_error"
    assert response.errors[0].field == "price"