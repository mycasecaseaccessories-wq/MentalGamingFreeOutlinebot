"""Application and migration version metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.core.constants import BOT_VERSION


@dataclass(frozen=True)
class VersionInfo:
    current: str
    migration: str
    build: str
    release: str

    def is_compatible_with(self, minimum: str) -> bool:
        """Compare simple numeric dotted versions without third-party deps."""
        def parts(value: str) -> tuple[int, ...]:
            numbers = value.split("-", 1)[0].split(".")
            return tuple(int(part) for part in numbers if part.isdigit())

        return parts(self.current) >= parts(minimum)


class VersionManager:
    def __init__(
        self,
        *,
        current: str = BOT_VERSION,
        migration: str = "0004",
        build: str = "dev",
        release: str = "development",
    ) -> None:
        self.info = VersionInfo(current, migration, build, release)

    @property
    def current(self) -> str:
        return self.info.current

    @property
    def migration(self) -> str:
        return self.info.migration

    @property
    def build(self) -> str:
        return self.info.build

    @property
    def release(self) -> str:
        return self.info.release

    def compatibility(self, minimum_versions: Iterable[str]) -> dict[str, bool]:
        return {
            version: self.info.is_compatible_with(version)
            for version in minimum_versions
        }


version_manager = VersionManager()