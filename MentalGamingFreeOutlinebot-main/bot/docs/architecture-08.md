# Phase 0.8 — Extension Ecosystem

Phase 0.8 adds metadata-driven registries and contracts without enabling any
business feature.

## Added foundations

- Command, menu, navigation, permission, and configuration registries.
- Explicit module/plugin discovery that never auto-enables discovered code.
- Generic module lifecycle contract.
- Dependency graph validation with missing/circular dependency detection.
- Extension SDK facade for registries, providers, events, and hooks.
- Transport-neutral Internal API facade.
- Webhook registry and HMAC signature primitives.
- Architecture Decision Record structure.

These components remain opt-in and preserve all Phase 0.1–0.7 APIs.
