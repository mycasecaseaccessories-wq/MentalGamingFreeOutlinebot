"""Webhook metadata registry and verification primitives."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WebhookDescriptor:
    name: str
    url: str
    events: tuple[str, ...] = ()
    enabled: bool = True
    secret: str | None = field(default=None, repr=False)
    max_retries: int = 3


class WebhookRegistry:
    def __init__(self) -> None:
        self._items: dict[str, WebhookDescriptor] = {}

    def register(self, descriptor: WebhookDescriptor) -> None:
        if descriptor.name in self._items:
            raise ValueError(f"Webhook already registered: {descriptor.name}")
        self._items[descriptor.name] = descriptor

    def unregister(self, name: str) -> bool:
        return self._items.pop(name, None) is not None

    def get(self, name: str) -> WebhookDescriptor:
        return self._items[name]

    def list(self, *, enabled_only: bool = False) -> list[WebhookDescriptor]:
        values = self._items.values()
        if enabled_only:
            values = (item for item in values if item.enabled)
        return sorted(values, key=lambda item: item.name)


def sign_payload(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, secret: str, signature: str) -> bool:
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


webhooks = WebhookRegistry()
