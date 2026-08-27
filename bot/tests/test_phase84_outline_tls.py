import base64
import hashlib

import pytest

from app.security.outline_tls import OutlineTLSIdentityError, normalize_fingerprint


def test_normalize_fingerprint_accepts_hex_and_sha256_prefix() -> None:
    digest = bytes(range(32))
    expected = digest.hex().upper()
    assert normalize_fingerprint(expected) == digest
    assert normalize_fingerprint(f"SHA256:{expected}") == digest


def test_normalize_fingerprint_accepts_base64_sha256_digest() -> None:
    digest = hashlib.sha256(b"outline-certificate").digest()
    assert normalize_fingerprint(base64.b64encode(digest).decode()) == digest


@pytest.mark.parametrize("value", [None, "", "not-a-fingerprint", "00", "SHA256:bad"])
def test_normalize_fingerprint_rejects_missing_or_malformed_values(value: str | None) -> None:
    with pytest.raises(OutlineTLSIdentityError):
        normalize_fingerprint(value)
