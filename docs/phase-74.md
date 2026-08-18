# Phase 7.4 — Backup & Disaster Recovery

## Scope

Phase 7.4 establishes a database-aware backup and disaster-recovery foundation. The implementation does not treat the existence of a dump file as proof of recoverability. A backup is represented by durable metadata and moves through creation, completion, checksum verification, and optional isolated restore testing. Production restore remains a controlled, approval-gated operation and is not an automatic destructive action.

## Implemented architecture

`BackupRecordORM` and migration `0035_phase74_backup_records` store public backup identity, backup type, detected database engine, lifecycle status, provider reference, size, SHA-256 checksum, encryption metadata, verification status, restore-test status, retention class, expiry, originating actor/job, safe error code, and a redacted manifest. Backup bytes are never stored in the database.

`NativeBackupProvider` uses SQLite's online backup API for SQLite databases. PostgreSQL and MySQL/MariaDB use native dump command hooks and return a safe `backup_tool_unavailable` or `native_backup_failed` result when the required tool is not available; the service never reports unsupported backup success. Storage is provider-based, with a local durable artifact provider currently implemented and a safe boundary for an off-site provider. `BACKUP_ENCRYPTION_KEY` enables Fernet encryption, `BACKUP_ENCRYPTION_KEY_VERSION` records key version metadata, and `BACKUP_REQUIRE_ENCRYPTION=true` can enforce encryption in production. Encryption keys are not stored in the database or backup manifest.

`BackupService` creates metadata before artifact generation, records success/failure without leaking secrets, verifies checksum and SQLite integrity, runs isolated SQLite restore tests, applies retention cleanup, exposes only safe backup summaries, prepares staging or production restore plans, and returns a report-only post-restore reconciliation boundary. Production preparation advertises the required maintenance lock, pre-restore protection, second-admin approval, and post-restore reconciliation requirements; it does not perform a destructive production restore.

Phase 7.3's durable scheduler now registers hourly automatic backups, daily retention cleanup, and weekly isolated restore-test jobs. Logical keys and leases come from the existing `BackgroundJobService`; no second scheduler or fulfillment system was introduced. Backup lifecycle events are emitted through the existing EventBus without artifact paths, credentials, encryption keys, or customer VPN secrets.

## Admin operations

The Admin menu includes a Backup & DR dashboard with manual backup creation, latest-backup verification, isolated restore-test execution, retention cleanup, refresh, safe status summaries, RPO/RTO display, and bounded failure messages. The UI exposes no raw storage path, database credential, encryption key, dump URL, or VPN secret. Production restore execution is intentionally not exposed as a one-click action; the service first prepares a controlled plan and requires the later approval/maintenance workflow.

## Post-restore reconciliation boundary

A database restore cannot restore current external state from Outline servers or a payment provider. The report-only reconciliation foundation therefore separates comparison from repair. Outline comparisons must cover missing remote keys, remote-only keys, lifecycle/expiry/data/device-limit mismatches, and revoked/active divergence. Payment comparisons must cover provider transaction identity, order/payment status, duplicate references, wallet ledger effects, rewards, and entitlements. Reward and entitlement reconciliation must use existing idempotency identities and authoritative providers; it must never blindly overwrite wallet balances, payment decisions, or VPN access.

## Default policy discussed

The proposed operating defaults are an off-site verified copy, RPO target of 15 minutes, normal RTO target of 60 minutes, second-admin approval for production restore, and retention classes of 48 hourly, 30 daily, 12 weekly, and 12 monthly backups. These are documented policy targets; an external off-site provider and production restore execution still require deployment-specific credentials and operational approval.

## Validation

Focused Phase 7.4 backup, scheduler, and restore-safety tests pass, including native SQLite backup creation, checksum corruption detection, isolated restore integrity, retention cleanup, production restore safety flags, post-restore report-only reconciliation, durable job lease/retry behavior, and scheduler integration. The complete Phase 0–7.4 regression suite passes with **465 tests passed and 32 warnings**. The warnings are existing datetime deprecations and do not indicate Phase 7.4 failures.

## Explicit boundaries

Phase 7.4 does not implement Phase 7.5 Maintenance & Incident Mode, a blind production restore, automatic external Outline repair, automatic payment-provider overwrite, or an unconfigured off-site storage integration. These boundaries are intentional because destructive recovery actions require provider-specific credentials, environment policy, maintenance coordination, and explicit approval.
