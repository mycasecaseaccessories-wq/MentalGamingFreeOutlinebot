"""TLS identity verification for Outline management endpoints."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import ipaddress
import socket
import ssl
from contextlib import suppress
from urllib.parse import urlsplit


class OutlineTLSIdentityError(ValueError):
    """Raised when an Outline server identity cannot be verified safely."""


def _digest_candidates(value: str) -> set[bytes]:
    raw = value.strip()
    if raw.upper().startswith("SHA256:"):
        raw = raw.split(":", 1)[1].strip()
    compact = raw.replace(":", "").replace(" ", "")
    candidates: set[bytes] = set()
    if len(compact) == 64:
        with suppress(ValueError):
            candidates.add(bytes.fromhex(compact))
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        decoded = b""
    if len(decoded) == hashlib.sha256().digest_size:
        candidates.add(decoded)
    return candidates


def normalize_fingerprint(value: str | None) -> bytes:
    """Return the expected SHA-256 digest or fail closed."""
    if not isinstance(value, str) or not value.strip():
        raise OutlineTLSIdentityError("Outline certificate fingerprint is required.")
    candidates = _digest_candidates(value)
    if len(candidates) != 1:
        raise OutlineTLSIdentityError("Outline certificate fingerprint is invalid.")
    return next(iter(candidates))


def _connect_and_digest(host: str, port: int, expected: bytes, timeout: float) -> None:
    try:
        ipaddress.ip_address(host)
        server_hostname = None
    except ValueError:
        server_hostname = host
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as raw, context.wrap_socket(
        raw, server_hostname=server_hostname
    ) as secured:
        certificate = secured.getpeercert(binary_form=True)
    if not certificate or not hashlib.sha256(certificate).digest() == expected:
        raise OutlineTLSIdentityError("Outline certificate fingerprint mismatch.")


async def verify_certificate_fingerprint(
    management_url: str,
    expected_fingerprint: str | None,
    *,
    timeout: float = 10.0,
) -> None:
    """Verify the live TLS certificate against the configured SHA-256 pin."""
    parsed = urlsplit(management_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise OutlineTLSIdentityError("Outline management API must use HTTPS.")
    expected = normalize_fingerprint(expected_fingerprint)
    port = parsed.port or 443
    try:
        await asyncio.to_thread(_connect_and_digest, parsed.hostname, port, expected, timeout)
    except OutlineTLSIdentityError:
        raise
    except (OSError, ssl.SSLError) as exc:
        raise OutlineTLSIdentityError("Outline certificate verification failed.") from exc
