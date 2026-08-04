---
name: Preference architecture
description: Design decisions for the user_preferences table and PreferenceService.
---

## Rule
One row per user in `user_preferences`. All preferences are typed columns — NOT a key-value EAV table and NOT a JSON blob. This keeps them queryable, indexable, and schema-enforced.

## Adding a new preference
1. Add a `Mapped` column to `UserPreferenceORM` (database/models/user_preference.py) with a sensible `default`.
2. Write an Alembic migration (`batch_alter_table` for SQLite compatibility).
3. Add the field to `UserPreference` domain dataclass (app/models/user_preference.py) with matching default.
4. Add a `PreferenceKey.<NAME>` constant and include it in `PreferenceKey.ALL`.
5. Add the key → default entry to `PreferenceService.DEFAULTS`.
6. Add validation in `PreferenceService._validate_value()` if the field has restricted values.

**Why:** Typed columns over EAV because preferences are read-heavy, must be bulk-queryable (e.g. `get_users_with_notifications()`), and need DB-level defaults for existing users.

## Cache pattern
`PreferenceService` keeps a per-instance `_cache: dict[int, UserPreference]`.
Invalidated on every write. Call `invalidate_cache(user_id)` when preferences are mutated outside the service.

## Services exposed in bot_data
`preference_service` added to `application.bot_data` in main.py alongside `user_service` and `language_service`.
