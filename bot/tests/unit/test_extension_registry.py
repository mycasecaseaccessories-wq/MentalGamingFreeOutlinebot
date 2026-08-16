from app.core.extension_registry import (
    CommandDescriptor,
    CommandRegistry,
    PermissionDescriptor,
    PermissionRegistry,
)
from app.core.dependency_graph import DependencyGraph, DependencyGraphError


def test_command_registry_registers_descriptor() -> None:
    registry = CommandRegistry()
    registry.register(CommandDescriptor(name="status"))
    assert registry.get("status").name == "status"


def test_permission_registry_grants_known_permission() -> None:
    registry = PermissionRegistry()
    registry.register(PermissionDescriptor(name="vpn.view"))
    registry.grant("admin", "vpn.view")
    assert registry.has("admin", "vpn.view")


def test_dependency_graph_orders_dependencies() -> None:
    graph = DependencyGraph()
    graph.add("core")
    graph.add("feature", ("core",))
    assert graph.topological_order() == ["core", "feature"]


def test_dependency_graph_rejects_cycle() -> None:
    graph = DependencyGraph()
    graph.add("a", ("b",))
    graph.add("b", ("a",))
    try:
        graph.validate()
    except DependencyGraphError:
        return
    raise AssertionError("cycle should be rejected")
