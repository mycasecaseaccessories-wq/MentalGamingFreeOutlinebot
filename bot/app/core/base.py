"""Framework-neutral base contracts for future modules."""

from __future__ import annotations

from abc import ABC
from typing import Any


class BaseHandler(ABC):
    """Marker base for handler objects; Telegram adapters live at the edge."""


class BaseKeyboard(ABC):
    """Marker base for keyboard builders; no business logic belongs here."""


class BaseMiddleware(ABC):
    """Marker base for middleware implementations."""


class BaseProvider(ABC):
    """Common provider identity used by provider registries."""

    provider_name: str = ""

    def health_details(self) -> dict[str, Any]:
        return {"provider": self.provider_name or self.__class__.__name__}