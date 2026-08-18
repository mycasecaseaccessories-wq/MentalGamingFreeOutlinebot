# Phase 7.5 — Maintenance & Incident Mode

## Implemented policy foundation

Phase 7.5 provides a durable maintenance policy source of truth. `MaintenanceWindowORM` stores typed scope/state/status, planned timing, customer-safe notices, alert-suppression policy, auto-end policy, and optional incident linkage. `OperationalIncidentORM` stores safe summaries, severity, customer impact, lifecycle timestamps, and administrative ownership without storing credentials or provider secrets.

The supported states are `NORMAL`, `DEGRADED`, `READ_ONLY`, `MAINTENANCE`, and `EMERGENCY`. Scopes include global, payments, wallet writes, VPN provisioning/lifecycle, orders, free trials, referrals, missions, promos, rewards, entitlements, notifications, jobs, backup, and administrative operations. Effective state considers both `GLOBAL` and the requested feature scope; the strongest active state wins, with the feature-specific window winning ties in the returned source metadata.

Migration `0036_phase75_maintenance_incidents` creates the maintenance and incident tables. Migration `0037_phase75_control_actions` adds durable maintenance-control actions with unique idempotency keys, actor/time indexes, action metadata, and audit linkage.

## Domain enforcement

Maintenance checks are performed below Telegram handlers at authoritative service boundaries:

| Boundary | Behavior during scoped maintenance | Safe operation behavior |
|---|---|---|
| Manual payment submission | New submissions return `maintenance_active` | Existing review can still be finalized |
| Wallet payment | New wallet spend returns `maintenance_active` | Read-only preview remains available |
| Order creation | New pending orders are blocked | Existing order reads remain available |
| Free Trial claim | Claim is rejected before quota or entitlement mutation | Existing keys and reads remain available |
| Paid VPN provisioning entry | New provisioning is blocked | Idempotent recovery remains owned by the provisioning saga |
| VPN lifecycle activation/extension | Customer/admin lifecycle writes are blocked | Expiry cleanup remains available as recovery work |
| Promo redemption | Reservation and reward mutation do not begin | Promo reads remain available |
| Mission progression/reward claim | New progress and claims are blocked | Mission read models remain available |
| Reward grants | New reward ledger fulfillment is blocked | Existing reward history remains readable |
| Entitlement consumption | New entitlement redemption is blocked | Entitlement history remains readable |
| Backup creation | New backup creation is blocked when backup maintenance is active | Verification, restore testing, and restore preparation remain available |

The existing payment-review finalization path is intentionally not blocked by payment maintenance. This preserves the distinction between **new payment initiation** and **finishing an already-reviewed financial decision**.

## Alert suppression and operations safety

`MaintenanceService.is_alert_suppressed()` evaluates active global/scoped windows and returns a structured suppression decision, alert key, scope, source window, and safe reason. Policies `scoped`, `global`, and `all` suppress expected alerts according to scope; `none` disables suppression. The result is designed for the Phase 7.2 alert evaluator to call before cooldown/deduplication and notification delivery.

Administrative schedule, end, and cancellation actions are recorded in `maintenance_actions` with idempotency keys and corresponding immutable `AuditLogORM` rows. Control actions are rate-limited to ten actions per actor per sixty seconds. Active-window end uses row locking, requires recovery checks, refuses unauthorized force/bypass requests, and preserves safe error codes. Scheduled activation also prevents a second active window for the same scope.

## Customer and admin UX

The Admin Maintenance & Incident Center is reachable from the existing admin menu. It provides active-window status, global emergency start, recovery-checked end, refresh, and active-incident listing. Customer navigation performs an early Free Trial maintenance check without globally disabling safe routes. Customer notices are localized in English and Burmese for default maintenance, degraded, and read-only states. Customer-facing responses never include credentials, provider URLs, or internal exception details.

## Scheduler and events

The Phase 7.3 durable scheduler activates due maintenance windows, processes expected ends, and records recovery snapshots. Lifecycle events include scheduled, started, ended, cancelled, recovery-failed, emergency, and incident lifecycle events. Maintenance checks are service-level policy calls and therefore remain effective even when Telegram handlers are bypassed or multiple workers execute concurrently.

## Verification

The focused Phase 7.5 suite covers global/scoped precedence, selective read-vs-write behavior, recovery-gated exit, scheduled activation, incident safe-summary retrieval, planned-alert suppression, control-action idempotency, immutable audit linkage, rate limiting, and force-bypass authorization. The complete Phase 0–7.5 regression suite passes with the required safe test configuration: **472 passed, 32 warnings**. Warnings are existing datetime deprecation notices and do not indicate Phase 7.5 failures.

## Scope note

The repository does not currently contain a concrete Phase 7.2 alert-evaluator/notification-delivery implementation; therefore the durable suppression decision API is implemented as the integration boundary rather than inventing a parallel alert system. `NotificationService` remains a framework placeholder and is not falsely reported as production delivery. Future Phase 7.6 work should connect the suppression decision to the actual alert evaluator when that service is introduced, then add production delivery and cooldown integration tests.
