# Phase 0.6.1 Architecture

Phase 0.6.1 adds extension points without enabling any business feature.
Existing services, handlers, repositories, and middleware continue to work.

## Plugins

Plugins expose a `PluginManifest` and inherit `BasePlugin`. Register plugins
with `PluginManager`; dependencies must be registered first. `setup()` is
called in registration order and `shutdown()` in reverse order.

```python
plugin = MyPlugin(PluginManifest(name="analytics", version="0.1.0"))
manager.register(plugin)
await manager.start_all(context)
```

The loader accepts modules exposing either a `plugin` instance or a
`create_plugin()` factory. No plugin is auto-loaded by default.

## Providers

`ProviderRegistry` stores named adapters by category and supports one default
provider per category. Consumers depend on the provider contract in
`app/core/interfaces.py`, not on a concrete Outline, Telegram, storage, or
payment implementation.

## Events and hooks

`EventBus` remains compatible with the existing `on()` and `emit()` API. New
subscriptions can specify a priority; higher numbers run first.
`EventDispatcher` adds `publish()` and `broadcast()` vocabulary.
`HookSystem` provides ordered extension hooks for future module boundaries.

## Dependency injection

`ServiceRegistry.resolve()` supports registered factories and lazy constructor
resolution while preserving `get()`, `register()`, and `initialise_all()`.

## Result and query contracts

`Result`, `Success`, `Failure`, `ValidationError`, `PermissionError`, and
`NotFound` make expected service outcomes explicit. Existing exception-based
services remain valid. `CursorPagination`, `PageInfo`, and typed filters are
transport contracts only; repositories still own query translation.

## Background work and discovery

`BaseTask`, `TaskRegistry`, and `BaseWorker` define future task/worker
lifecycle APIs without adding scheduled jobs. `FeatureRegistry` and
`ModuleRegistry` provide discoverable feature/module metadata and dependency
checks.