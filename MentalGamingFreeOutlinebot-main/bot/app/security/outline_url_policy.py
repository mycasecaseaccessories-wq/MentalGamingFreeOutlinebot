"""Validation and outbound-target policy for admin-provided Outline URLs."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit


class UnsafeOutlineURL(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ValidatedOutlineURL:
    value: str
    scheme: str
    host: str
    port: int
    path: str


def _blocked_ip(address: str, *, allow_private: bool) -> bool:
    ip = ipaddress.ip_address(address)
    if ip.is_unspecified or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_private and not allow_private:
        return True
    return False


async def validate_outline_url(raw: str, *, allow_private: bool = False, resolve_dns: bool = True) -> ValidatedOutlineURL:
    if not isinstance(raw, str) or len(raw) > 2048 or any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise UnsafeOutlineURL("Management URL is invalid.")
    value = raw.strip()
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"https", "http"} or parsed.username or parsed.password or parsed.fragment or not parsed.hostname:
        raise UnsafeOutlineURL("Only HTTP(S) management URLs with a host are supported.")
    if parsed.query:
        raise UnsafeOutlineURL("Management URL must not contain a query string.")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise UnsafeOutlineURL("Management URL port is invalid.") from exc
    if not 1 <= port <= 65535 or not parsed.path or parsed.path == "/":
        raise UnsafeOutlineURL("Management URL must include a non-empty credential path and valid port.")
    host = parsed.hostname.rstrip(".").lower()
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        parsed_ip = None
    if parsed_ip is not None:
        if _blocked_ip(host, allow_private=allow_private):
            raise UnsafeOutlineURL("Management URL targets a prohibited network address.")
    elif resolve_dns:
        try:
            infos = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeOutlineURL("Management URL host could not be resolved.") from exc
        for info in infos:
            address = info[4][0]
            if _blocked_ip(address, allow_private=allow_private):
                raise UnsafeOutlineURL("Management URL resolves to a prohibited network address.")
    return ValidatedOutlineURL(value=value, scheme=parsed.scheme.lower(), host=host, port=port, path=parsed.path)
