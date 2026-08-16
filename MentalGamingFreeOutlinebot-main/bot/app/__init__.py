"""
Application package.

Contains all bot logic split into focused sub-packages:
  handlers    — Telegram update handlers (commands, messages, callbacks)
  services    — Business logic layer
  repositories — Data access layer (repository pattern)
  models      — Domain data models
  keyboards   — Inline / reply keyboard builders
  middlewares — Cross-cutting concerns (auth, rate-limiting, i18n)
  utils       — Shared utilities (logger, helpers)
  scheduler   — Background / scheduled tasks
"""
