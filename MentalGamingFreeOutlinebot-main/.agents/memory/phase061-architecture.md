---
name: Phase 0.6.1 architecture
description: Extension points added for plugins, providers, events, hooks, results, discovery, and background work.
---

Phase 0.6.1 keeps existing service/handler/repository APIs intact and adds opt-in contracts: plugins use manifest plus setup/shutdown lifecycle, providers are selected by named category/default, EventBus priorities run higher values first, and Result is for new service boundaries while existing exception flows remain valid.

**Why:** The project needs future feature modules without coupling them to Telegram, ORM, or concrete infrastructure providers, while preserving all previous phases.

**How to apply:** Register only real feature plugins/providers/tasks when the corresponding phase begins; do not auto-load or enable business features from the foundation layer.