---
name: Alembic startup pattern
description: How migrations run at startup and what to update when adding a new migration.
---

## Rule
`DatabaseManager.init()` runs `alembic upgrade head` in a thread executor.
If an existing DB has no `alembic_version` table it is stamped at `0001` first (Phase 0.2 compatibility).

## What to update when adding migration NNNN
1. Write `bot/database/migrations/versions/NNNN_*.py`.
2. Update the HEAD assertion in `bot/tests/test_settings_phase03.py` (two lines mentioning the old HEAD).
3. Update `_build_phase02_db` in the same test file if NNNN touches a table that the Phase 0.2 simulation doesn't include.

**Why:** The Phase 0.2 simulation only creates tables that the test helper explicitly defines; if a new migration ALTERs a table not in the helper, the test fails with "no such table".

**How to apply:** After writing any new migration, search `test_settings_phase03.py` for the previous HEAD string and bump it.
