# Production Readiness Evidence Contract

Production readiness is an evidence verdict, not a claim inferred from implementation. The only valid outcomes are `READY`, `READY_WITH_WARNINGS`, and `NOT_READY`. The gate must never return `READY` when the required test run, alert evaluator, notification delivery path, or ten-key provider-recovery flow is missing.

## Required operational flow

The authoritative controlled flow is:

`HealthService provider failure → OperationalAlertService alert OPEN → MaintenanceService incident OPEN → scoped VPN provisioning maintenance ACTIVE → MaintenanceService EN/MY customer-safe notice → provider recovery through HealthService → provider-aware recovery_check → MaintenanceService end → alert RESOLVED → incident RESOLVED`.

The flow is now executable in the integration test `test_outline_failure_full_operational_recovery_flow`. It uses a controlled HealthService provider probe, the concrete persisted alert evaluator, MaintenanceService incident and maintenance operations, the localized customer notice path, and recovery resolution. The scheduler health-job bridge also invokes the evaluator in application operation.

## Truthful availability

`ProductionOperationsSnapshot.alerts.available` is true only when both the concrete evaluator/repository and its notification delivery adapter are initialized. The snapshot separately reports `evaluator_available`, `notification_available`, open-alert count, and a safe reason when availability is false. A class existing in the registry without a configured delivery path is not considered operationally available.

## Evidence tests

The focused evidence suite covers persisted alert deduplication, ten repeated failures producing one logical alert and one incident, delivery failure and retry, open/recovery notification idempotency, HealthService-driven failure and recovery, scoped maintenance, EN/MY customer messaging, incident resolution, operations snapshot truth, and notification recipient routing. Negative Phase 7.6 readiness tests remain in place for missing test evidence, missing flow evidence, unavailable alert evaluator, unhealthy health, stopped scheduler, stopping lifecycle, and dead-letter evidence.

## Current limitation

The controlled integration evidence proves the application flow using an explicit provider adapter. It is not a claim that a live external Outline deployment has been taken offline in this sandbox. External-provider credentials, test transport routing, and production infrastructure execution remain deployment-specific evidence requirements. Those limitations must remain visible in the final verdict.
