---
name: Middleware registration
description: How PTB v21 middleware works and the required execution order.
---

## Pattern
```python
application.add_handler(TypeHandler(Update, auth_middleware_handler),     group=-1)
application.add_handler(TypeHandler(Update, language_middleware_handler), group=-1)
application.add_handler(TypeHandler(Update, activity_middleware_handler), group=-1)
```

PTB v21 processes handlers in group order (lowest first), so group=-1 fires before all regular handlers in group 0+.

## Context keys set by middleware
- `context.user_data["platform_user"]` — User domain object (set by auth middleware)
- `context.user_data["translator"]` — Translator bound to user's language (set by language middleware)

## Execution order is important
1. **auth** — must run first; resolves platform_user; blocks banned/suspended.
2. **language** — reads platform_user.language; attaches Translator.
3. **activity** — stamps last_active; fire-and-forget (errors are swallowed).

**Why:** language and activity middlewares depend on platform_user being present in user_data.

## Shared services in bot_data
`application.bot_data` holds `db`, `user_service`, `language_service`.
Handlers and middlewares read them as `context.bot_data["user_service"]`.
