# Testing and Quality

Phase 0.7 establishes unit, integration, compatibility, security, snapshot,
golden-file, property-based, and performance test foundations.

The CI quality gate runs linting, formatting verification, type checking,
tests with coverage, and byte-code compilation. The configured coverage gate
is 90%.

Local quality command:

```bash
ruff check bot
ruff format --check bot
mypy bot/app
pytest bot/tests --cov=bot/app --cov-report=term-missing
```
