from datetime import datetime, timezone

import pytest

from app.integrations.outline_provider import OutlineProvider
from app.models.vpn_provisioning import ProvisioningSource, RemoteVPNKeyResult, VPNProvisioningRequest


def test_request_requires_persistent_idempotency_and_reference():
    with pytest.raises(ValueError):
        VPNProvisioningRequest(user_id=7, source_type=ProvisioningSource.ADMIN).validate()


def test_request_rejects_unsupported_provider_and_unbounded_attempts():
    with pytest.raises(ValueError):
        VPNProvisioningRequest(
            user_id=7,
            source_type=ProvisioningSource.ADMIN,
            provider_type="unknown",
            idempotency_key="idem",
            request_reference="req",
        ).validate()
    with pytest.raises(ValueError):
        VPNProvisioningRequest(
            user_id=7,
            source_type=ProvisioningSource.ADMIN,
            idempotency_key="idem",
            request_reference="req",
            max_server_attempts=9,
        ).validate()


def test_outline_key_name_is_safe_and_deterministic():
    name = OutlineProvider.safe_key_name(
        public_order_id="ORD-SECRET-123", operation_id="VP-op"
    )
    assert name.startswith("MG-ORD-")
    assert "SECRET" not in name
    assert len(name) <= 64
    assert name == OutlineProvider.safe_key_name(
        public_order_id="ORD-SECRET-123", operation_id="VP-other"
    )


def test_remote_result_repr_redacts_access_url():
    value = RemoteVPNKeyResult(
        42,
        "ss://SECRET_TOKEN@host:123/x",
        "outline",
        datetime.now(timezone.utc),
    )
    assert "SECRET_TOKEN" not in repr(value)
    assert "42" in repr(value)


def test_phase41_migration_chain_exists():
    from pathlib import Path

    root = Path(__file__).parents[1] / "database/migrations/versions"
    assert (root / "0016_phase41_provisioning_operations.py").exists()
    assert (root / "0017_phase41_vpn_key_binding.py").exists()
