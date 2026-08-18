# Phase 7.2 — Operational Alerting

Phase 7.2 now has a concrete operational alert path. `OperationalAlertService` consumes authoritative `HealthCheckResult` values, derives deterministic logical fingerprints, persists `OperationalAlertORM` rows, deduplicates repeated failures, creates and resolves incidents through `MaintenanceService`, and starts scoped VPN provisioning maintenance for Outline provider outages.

Migration `0038_phase72_operational_alerts` adds durable alert identity, lifecycle, severity, safe summary, incident linkage, and recovery metadata. Migration `0039_phase72_alert_notification_cycles` adds durable notification-cycle state and attempt counters so successful open/recovery notifications are idempotent while failed delivery remains retryable.

The existing Telegram bot client is reused by `NotificationService`; no second provider client is created. Admin routing is derived from configured settings, delivery is bounded by transient retries, and results expose only safe delivery evidence. Customer-facing messages continue through `MaintenanceService.get_customer_notice()` and the existing EN/MY localization path; management URLs, credentials, access keys, raw exceptions, and provider secrets are not included.

The durable scheduler health job now runs the real `HealthService.check_system()` path and passes the Outline health result to `OperationalAlertService.evaluate_health_result()`. Repeated unhealthy evaluation creates one logical alert, one linked active incident, and one successful open-notification cycle. Recovery resolves the original alert and incident, runs a provider-aware recovery check, ends the scoped maintenance window, and emits at most one recovery notification cycle.

Focused evidence includes a real HealthService-driven provider failure and recovery test, ten-run deduplication, delivery-failure retry, EN/MY customer-safe messages, operations snapshot truth, and notification adapter routing tests.
