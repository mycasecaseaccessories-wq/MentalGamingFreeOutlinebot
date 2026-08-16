"""Worker lifecycle contract for future queues and schedulers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseWorker(ABC):
    name: str = ""

    @abstractmethod
    async def start(self) -> None:
        """Start accepting work."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop accepting work and release resources."""

    async def health(self) -> dict[str, Any]:
        return {"name": self.name or self.__class__.__name__, "running": True}