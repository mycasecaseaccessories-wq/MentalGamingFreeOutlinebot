# Phase 7.1 — System Health & Operational Dashboard

## Scope and boundary

Phase 7.1 establishes a read-only operational visibility foundation. It does not automatically repair services, restart workers, retry failed jobs, send alerts, or change customer access. Those behaviors belong to later operational phases, especially Phase 7.2 alerting and Phase 7.3 scheduler hardening.

The implementation extends the existing `HealthService` instead of introducing a parallel monitoring system. Its legacy `HealthReport` and `HealthStatus` APIs remain available for compatibility. Phase 7.1 adds typed operational results through `OperationalHealthStatus`, `HealthCheckResult`, and `HealthSnapshot`.

## Health model

Each component result contains a bounded component name, typed status, UTC check time, optional latency, stable message code, safe details, optional safe error code, freshness deadline, and criticality. Raw exception text, database URLs, credentials, Telegram tokens, Outline management URLs, and provider secrets are never returned to the Admin UI.

The supported operational states are **HEALTHY**, **DEGRADED**, **UNHEALTHY**, **UNKNOWN**, **DISABLED**, and **STALE**. Overall state is derived from component state rather than process liveness alone. An unhealthy critical component makes the system unhealthy. A degraded, stale, or unknown component makes the system degraded unless a critical unhealthy state has already taken precedence.

## Implemented checks

The Phase 7.1 snapshot checks the existing database with a lightweight `SELECT 1` operation and records bounded latency. Telegram bot connectivity uses the existing injected Bot object and a metadata-only `get_me()` call; it does not send a customer message. Worker visibility reuses the injected scheduler and reports whether its established scheduler backend is running. If a dependency is not injected, the result is explicitly **UNKNOWN** rather than falsely healthy.

VPN server visibility reuses the existing `ServerORM` and Phase 3.5 synchronization fields. The dashboard reports total, healthy, unhealthy, and stale registered servers without reimplementing Outline synchronization. Outline API, payment provider, and notification provider checks report an explicit `provider_probe_unavailable` state when the repository has no safe provider-health contract yet. This is intentional: Phase 7.1 must not claim that an unsupported provider probe succeeded.

Operational aggregates reuse the existing provisioning-operation table. Failed jobs count failed and compensation-required provisioning operations. Stale operations count long-running transitional operations older than the bounded freshness threshold. Capacity aggregates reuse registered server user/key limits and current counts, returning utilization percentages only where a configured maximum exists.

## Admin dashboard

The existing Admin menu now exposes **System Health**. The Admin-only handler renders an overview with overall state, Bot, Database, Workers, VPN Servers, Outline APIs, Payments, Notifications, failed jobs, stale operations, and last updated time. Drill-down callbacks provide server summary, worker status, provider-probe status, failure counts, and capacity utilization. Refresh performs a safe manual snapshot and does not mutate business or customer state.

All callbacks use the existing `admin_required` permission boundary. Callback payloads contain only fixed component identifiers. No credentials or user-sensitive operational internals are placed in Telegram callback data. English and Myanmar localization covers the menu, status lines, drill-downs, capacity, failures, freshness, and unavailable-component outcomes.

## Validation

The Phase 7.1 focused suite contains five tests covering typed status bounds, derived overall health, lightweight database timing, database exception redaction, and explicit unsupported-provider behavior. The full Phase 0–7.1 regression suite completed with **458 passed tests and 32 warnings**. Python compilation completed successfully.

## Phase 7.2 handoff

The health snapshot is now the foundation for monitoring and alerting. Phase 7.2 may subscribe to health transitions and operational aggregates to implement Server Down, capacity-low, worker-dead, provisioning-failure-spike, payment-failure-spike, cooldown, deduplication, and Admin notification behavior. It should not duplicate `HealthService`, should use stable component/error codes, and should preserve the Phase 7.1 rule that unknown provider capability is not silently treated as healthy.
