"""Dependency graph validation for platform modules and plugins."""

from __future__ import annotations

from dataclasses import dataclass


class DependencyGraphError(ValueError):
    """Raised when a dependency graph is invalid."""


@dataclass(frozen=True)
class DependencyIssue:
    kind: str
    module: str
    dependency: str | None = None


class DependencyGraph:
    def __init__(self) -> None:
        self._graph: dict[str, set[str]] = {}

    def add(self, name: str, dependencies: tuple[str, ...] = ()) -> None:
        self._graph[name] = set(dependencies)

    def missing(self) -> list[DependencyIssue]:
        names = set(self._graph)
        return [
            DependencyIssue("missing", module, dependency)
            for module, dependencies in self._graph.items()
            for dependency in sorted(dependencies - names)
        ]

    def topological_order(self) -> list[str]:
        missing = self.missing()
        if missing:
            first = missing[0]
            raise DependencyGraphError(
                f"{first.module!r} depends on missing module {first.dependency!r}"
            )

        temporary: set[str] = set()
        permanent: set[str] = set()
        ordered: list[str] = []

        def visit(node: str) -> None:
            if node in permanent:
                return
            if node in temporary:
                raise DependencyGraphError(f"Circular dependency detected at {node!r}")
            temporary.add(node)
            for dependency in sorted(self._graph[node]):
                visit(dependency)
            temporary.remove(node)
            permanent.add(node)
            ordered.append(node)

        for node in sorted(self._graph):
            visit(node)
        return ordered

    def validate(self) -> None:
        self.topological_order()
