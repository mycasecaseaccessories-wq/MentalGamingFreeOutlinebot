# Phase 7.4 Specification Notes

Source: user-provided attachment `Pasted_content_49.txt` / Phase 7.4 Final Manus Prompt.

The primary safety rule is that a backup is not healthy merely because an artifact exists. A valid backup must be created, completed, stored, integrity checked, and represented by durable metadata; periodic isolated restore testing should prove that the artifact can actually be restored. The implementation must detect the real database engine and use its native safe strategy: PostgreSQL native dump/snapshot, MySQL/MariaDB transaction-consistent native dump, or SQLite online backup API rather than blindly copying a live file.

The prompt requires a provider abstraction, durable BackupRecord metadata, typed statuses and backup types, checksum and encryption metadata without storing encryption keys in the database, retention and cleanup, controlled restore workflow, restore verification, Admin visibility, failure monitoring/alerts, security/audit, RPO/RTO documentation, and no duplicate backup infrastructure.

The critical restore boundary is cross-system reconciliation. A database restore cannot automatically restore the current state of external Outline VPN servers or payment-provider transactions. After restore, the system must compare DB intent with remote Outline keys/lifecycle/limits and compare provider transaction IDs, order/payment states, wallet ledger effects, rewards, entitlements, and idempotency identities. The first mode is report-only/dry-run. Destructive repair, key revoke/create, payment overwrite, wallet correction, or reward replay requires explicit safe domain operations and Admin approval; blind overwrite is prohibited.

The current policy discussion proposed an off-site verified copy, RPO target of 15 minutes, normal RTO target of 60 minutes, second-Admin approval for production restore, and retention of 48 hourly, 30 daily, 12 weekly, and 12 monthly backups. These are design defaults to validate before production rollout.
