---
name: Bot stack conventions
description: Key conventions for the Mental VPN Bot codebase — middleware order, service access, logging.
---

## Middleware registration order

| Group | Middleware | Purpose |
|-------|-----------|---------|
| -2 | `request_context_middleware_handler` | Stamp request_id — MUST be first |
| -1 | `auth_middleware_handler` | Resolve platform_user, block banned |
| -1 | `language_middleware_handler` | Attach Translator |
| -1 | `activity_middleware_handler` | Stamp last_active |
| 0+ | business handlers | |

## Accessing services in handlers

```python
registry = context.bot_data["registry"]
user_svc = registry.get(UserService)
cache    = context.bot_data["cache"]
```

## Logging convention

Every log line has `[request_id]` auto-injected by `RequestIdFilter`. During startup (no active request), it shows `[-]`.

## Bot command

Run from repo root: `cd bot && python main.py`
Or from bot/ dir: `python main.py`

## Phase status

0.1–0.5 complete. Phase 1 next = user registration + language selection flow.
