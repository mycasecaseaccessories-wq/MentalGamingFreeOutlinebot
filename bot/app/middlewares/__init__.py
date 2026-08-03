"""
Middlewares package.

Middlewares are cross-cutting concerns applied to every (or many) incoming
updates before the handler sees them.

Current middleware:
    auth     — Injects the platform User object into context.user_data.
    logging  — Logs every incoming update at DEBUG level.

Adding new middleware:
    1. Create a module in this package.
    2. Export the function here.
    3. Register it in main.py via application.add_handler() or a custom
       post_init / pre_process_update hook.

NOTE: python-telegram-bot v21 middleware support uses TypeHandler and
      custom Application subclasses.  Full implementation is Phase 0.2.
"""
