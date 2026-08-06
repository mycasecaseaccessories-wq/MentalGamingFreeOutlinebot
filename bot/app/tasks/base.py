"""Background task contracts without scheduling business jobs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    REGISTERED = "registered"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskContext:
    task_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTask(ABC):
    name: str = ""

    @abstractmethod
    async def run(self, context: TaskContext) -> Any:
        """Execute one task invocation."""


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, BaseTask] = {}

    def register(self, task: BaseTask) -> None:
        name = task.name or task.__class__.__name__
        if name in self._tasks:
            raise ValueError(f"Task {name!r} is already registered")
        self._tasks[name] = task

    def get(self, name: str) -> BaseTask:
        return self._tasks[name]

    def list(self) -> list[str]:
        return sorted(self._tasks)