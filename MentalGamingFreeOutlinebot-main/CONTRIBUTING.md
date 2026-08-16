# Contributing

## Development workflow

1. Create a branch from the current development branch.
2. Install the project with development dependencies.
3. Keep handlers thin, business logic in services, and database access in repositories.
4. Add or update tests for every behavior change.
5. Run the quality gate before opening a review.

## Quality gate

```bash
ruff check bot
ruff format --check bot
mypy bot/app
pytest bot/tests --cov=bot/app --cov-report=term-missing
```

The coverage target is 90% or higher. New code must not reduce the project below the configured gate.

## Commit convention

Use Conventional Commit style where practical:

- `feat: ...`
- `fix: ...`
- `refactor: ...`
- `test: ...`
- `docs: ...`
- `chore: ...`

## Architecture rules

- Telegram handlers adapt input/output only.
- Services own application/business orchestration.
- Repositories own persistence access.
- Plugins extend behavior through registries, hooks, events, or provider contracts.
- Do not introduce circular dependencies.
- Never commit secrets.
