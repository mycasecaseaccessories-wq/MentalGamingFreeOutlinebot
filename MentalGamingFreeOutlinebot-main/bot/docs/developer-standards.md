# Developer Standards

These rules apply to all future Mental Outline VPN modules.

## Layer boundaries

| Concern | Home | Rule |
|---|---|---|
| Business logic | `app/services/` | Services orchestrate use cases and depend on contracts. |
| Database access | `database/repositories/` | SQL and ORM queries stay in repositories. |
| Telegram updates | `app/handlers/` | Handlers translate Telegram input/output and call services. |
| Telegram UI | `app/keyboards/` | Keyboard builders contain presentation structure only. |
| Cross-cutting concerns | `app/middlewares/` | Middleware enriches or gates a request; it does not implement a feature. |
| Reusable helpers | `app/core/` | Keep helpers stateless and independent of Telegram/ORM details. |

## Naming and structure

- Use `snake_case` for files, functions, variables, and database columns.
- Use `PascalCase` for classes, DTOs, and exception types.
- Use `UPPER_SNAKE_CASE` for module constants and environment variable names.
- One module should have one clear responsibility; avoid “misc” feature modules.
- New domain enums belong in `app/models/enums.py`; new transport DTOs belong in
  `app/core/schemas.py`.

## Dependencies and interfaces

- Inject database managers, providers, and services; do not construct them in
  handlers or repositories.
- Depend on `app/core/interfaces.py` when a feature may have multiple providers.
- Services must not issue SQL directly, and repositories must not contain
  Telegram/UI behavior.
- Avoid circular imports. Use a local import only when it is genuinely needed
  to break an optional dependency cycle.

## Errors and logging

- Raise a specific `app.core.exceptions.AppException` subclass instead of a
  bare `Exception` for expected application failures.
- Use the centralized logger; never use `print()` in application modules.
- Never log bot tokens, passwords, session secrets, access URLs, or raw user
  credentials. Use `app.core.security.redact_sensitive()` or masking helpers.
- Include useful structured context such as `request_id` without duplicating
  secrets in `extra`.

## Validation and data contracts

- Validate external input at the boundary with `app/core/validators.py` or a
  Pydantic DTO.
- Use `StandardResponse` for service/API response envelopes and
  `PaginationParams` / `PaginatedResult` for collection boundaries.
- Keep DTOs transport-safe; do not expose ORM internals as public contracts.
- Use timezone-aware UTC timestamps for new cross-layer contracts.

## Tests and compatibility

- Add focused tests under `bot/tests/` for each reusable foundation component.
- Preserve compatibility with the existing async SQLAlchemy and
  `python-telegram-bot` stack.
- Run `cd bot && uv run pytest -q` before merging.