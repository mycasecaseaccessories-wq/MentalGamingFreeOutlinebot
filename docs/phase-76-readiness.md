# Phase 7.6 — Production Operations Readiness Evidence

## Current verdict

> **NOT_READY**

The verdict remains `NOT_READY` because the sandbox has proven the complete controlled application flow but has not executed a live external Outline deployment outage. The readiness gate is intentionally not weakened: missing live-provider evidence remains a deployment-specific blocker even though the concrete evaluator, notification path, incident linkage, maintenance response, and recovery logic now exist and pass controlled integration tests.

## Concrete implementation

`ProductionOperationsService` remains a thin aggregation and verdict layer. It reuses `HealthService`, durable jobs, the existing scheduler, `BackupService`, `MaintenanceService`, lifecycle state, settings, and the concrete `OperationalAlertService`. The scheduler's durable health job now executes `HealthService.check_system()` and passes the Outline result into `OperationalAlertService.evaluate_health_result()`.

`OperationalAlertService` persists deterministic alert fingerprints, deduplicates repeated failures, creates and resolves incidents through `MaintenanceService`, starts scoped VPN provisioning maintenance for Outline outages, and performs provider-aware recovery checks before ending maintenance. `NotificationService` reuses the configured Telegram bot, routes to configured administrators, retries bounded transient failures, and returns safe delivery evidence. Durable alert notification-cycle fields in migration `0039_phase72_alert_notification_cycles` prevent successful open/recovery notification spam while allowing failed delivery to retry.

The operations snapshot reports `alerts.available=true` only when both the evaluator/repository and notification adapter are initialized. It separately exposes evaluator and notification availability, open-alert count, and a safe unavailable reason.

## Controlled end-to-end evidence

The integration test `test_outline_failure_full_operational_recovery_flow` executes the authoritative HealthService path with a controlled provider adapter, then the concrete alert, incident, maintenance, customer-message, recovery, and resolution services.

| Evidence key | Result | Evidence source |
|---|---:|---|
| `health_detected` | `true` | `HealthService.check_system()` returns Outline `UNHEALTHY` after controlled failure injection |
| `alert_opened` | `true` | `OperationalAlertService.evaluate_health_result()` persists one `OPEN` alert |
| `incident_opened` | `true` | `MaintenanceService.create_incident()` and linked `incident_id` |
| `maintenance_started` | `true` | `MaintenanceService.schedule_maintenance()` creates active VPN provisioning scope |
| `customer_notified` | `true` | `MaintenanceService.get_customer_notice()` returns safe EN and MY messages |
| `provider_recovered` | `true` | `HealthService.check_system()` returns Outline `HEALTHY` after removal of injected failure |
| `recovery_checked` | `true` | `MaintenanceService.recovery_check(provider_healthy=True, queue_healthy=True)` passes |
| `maintenance_ended` | `true` | `MaintenanceService.end_maintenance(..., recovery_ok=True)` completes the active window |
| `alert_resolved` | `true` | Original persisted alert transitions to `RESOLVED` |
| `incident_resolved` | `true` | Linked incident is resolved through `MaintenanceService` |

Additional evidence tests prove ten repeated failures create one logical alert, one incident, and one successful notification cycle; failed delivery leaves the alert open and retries without creating a duplicate; recovery notification is idempotent; EN/MY customer notices contain no provider secrets; and the operations snapshot reports truthful alert, incident, and maintenance state.

## Validation

| Validation | Result |
|---|---:|
| Focused Phase 7.2 alert/notification suite | **7 passed** |
| Focused Phase 7.5 maintenance suite | **5 passed** |
| Focused Phase 7.6 readiness suite | **5 passed** |
| Full Phase 0–7.6 regression after all implementation and evidence tests | **487 passed** |
| Additional Phase 7.2 evidence tests | **8 passed**, including controlled ten-key readiness verdict |
| Static compilation | Passed |
| `git diff --check` | Passed |
| Ruff lint/format | Not run: `ruff` unavailable in sandbox |
| Mypy type-check | Not run: `mypy` unavailable in sandbox |
| Known warnings | **32 existing datetime deprecation warnings** |

The final full regression was rerun after the last implementation and evidence-test changes. The verdict remains `NOT_READY` until live external-provider evidence is captured.

## Negative readiness evidence retained

The gate continues to return `NOT_READY` for missing test evidence, missing flow evidence, unavailable alert evaluator or notification delivery, unhealthy critical health, stopped scheduler, stopping lifecycle, and unsafe operational states. A passing regression suite alone never produces `READY`.

## Remaining blocker

The controlled failure-injection flow uses an explicit provider adapter in the repository test environment. It proves the real application services and persistence path, and the controlled readiness test produces `READY` or `READY_WITH_WARNINGS` only after all ten evidence keys are derived from service results. It does not claim that a real external Outline Management API was taken offline and restored in a production-like environment. A deployment-specific evidence run with the actual provider adapter, notification transport, and configured administrator routing is still required before the overall repository verdict can become `READY` or `READY_WITH_WARNINGS`.
