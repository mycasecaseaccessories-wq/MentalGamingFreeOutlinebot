"""Validation policy for admin-provided VPS SSH targets."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket

from app.models.ssh_discovery import SSHCredentialInput


class UnsafeSSHTarget(ValueError):
    pass


_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}[A-Za-z0-9]$")
_USER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,31}$")


def validate_ssh_input(value: SSHCredentialInput, *, allow_private: bool = False) -> SSHCredentialInput:
    host = value.host.strip().rstrip(".")
    if not host or len(host) > 253 or not _HOST_RE.match(host) or any(ord(ch) < 32 for ch in host):
        raise UnsafeSSHTarget("SSH host is invalid.")
    if not 1 <= value.port <= 65535:
        raise UnsafeSSHTarget("SSH port must be between 1 and 65535.")
    username = value.username.strip()
    if not _USER_RE.match(username):
        raise UnsafeSSHTarget("SSH username is invalid.")
    if value.auth_method == "password" and not value.password:
        raise UnsafeSSHTarget("SSH password is required.")
    if value.auth_method == "private_key" and not value.private_key:
        raise UnsafeSSHTarget("SSH private key is required.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and _blocked(ip, allow_private=allow_private):
        raise UnsafeSSHTarget("SSH target address is not allowed.")
    return SSHCredentialInput(host=host, port=value.port, username=username, auth_method=value.auth_method, password=value.password, private_key=value.private_key, key_passphrase=value.key_passphrase, expected_host_key_fingerprint=value.expected_host_key_fingerprint)


def _blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_private: bool) -> bool:
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return True
    return ip.is_private and not allow_private


async def resolve_and_validate_host(host: str, port: int, *, allow_private: bool = False) -> None:
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeSSHTarget("SSH host could not be resolved.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if _blocked(address, allow_private=allow_private):
            raise UnsafeSSHTarget("SSH host resolves to a prohibited network address.")
