# Phase 7.3 — Background Jobs & Scheduler Hardening

## Scope

Phase 7.3 hardens deterministic background work without moving business rules into the scheduler. The implementation keeps VPN lifecycle, order, trial recovery, server synchronization, reservation cleanup, health, growth, payment, mission, and promo services as the authoritative domain owners. The scheduler only creates durable logical jobs and dispatches them through leases.

## Durable job contract

The new `background_jobs` table stores a safe job type, unique logical key, status, priority, sanitized payload, schedule and availability timestamps, attempt counters, maximum attempts, timeout, lease ownership, lease expiry, heartbeat, correlation identifier, and bounded error metadata. Revision `0034_phase73_background_jobs` follows the Phase 6.6 migration head.

A logical key is unique, so repeated enqueue requests converge on one row. Periodic scheduler ticks use a time bucket in the logical key, allowing restart-safe missed work without creating duplicate executions for the same bucket. Payloads are operational identifiers only; credentials, tokens, VPN keys, payment proofs, and customer secrets are not stored in the job payload.

## Lease and retry behavior

`BackgroundJobService.acquire()` selects one due job under a database row lock, assigns a worker owner, increments the attempt count, and records a bounded lease expiry. A worker must mark the lease running and can heartbeat it. Completion is owner-safe and idempotent. Failure records a short error code and message, schedules bounded exponential backoff, or transitions to failed/dead-letter when retry policy is exhausted. Expired leases are requeued immediately or dead-lettered when the attempt budget is exhausted.

The durable dispatcher is safe to run from multiple instances because business work is entered only after lease acquisition. Worker or process crashes leave a leased row that a later recovery pass can reclaim. This protects downstream idempotent business services from scheduler retries and prevents a second reward, wallet credit, VPN key, or entitlement effect when the same logical work is encountered again.

## Registered authoritative jobs

The hardened scheduler routes existing operations through durable jobs where safe contracts already exist: Outline/server synchronization, server-reservation cleanup, VPN-key expiration, pending-order expiration, free-trial upgrade fulfillment recovery, and health snapshots. Additional reward, promo, mission, alert, and reconciliation jobs must be registered only after their domain services expose an explicit bounded, system-safe operation; no unsupported business mutation is fabricated in Phase 7.3.

## Admin operations

Admins can open the Background Jobs view from the existing Admin menu. The view exposes bounded status counts and safe identifiers, refreshes the current list, and allows stale-lease recovery. It does not expose payload secrets, credentials, customer VPN keys, or raw exception traces. Recovery is Admin-only and emits the existing EventBus operational lifecycle events.

## Observability and safety

The existing EventBus now carries background-job enqueue, completion, failure, dead-letter, and stale-lease-recovery events. The implementation deliberately does not add a second telemetry system. The job service remains read-only with respect to domain data, and all business effects remain delegated to existing transactional/idempotent services. There is no customer-facing behavior change from a scheduler tick alone.

## Validation

Focused Phase 7.3 tests cover concurrent logical-key enqueue deduplication, owner-safe completion, retry backoff, dead-letter transition, and stale-lease recovery. The focused suite passed with `3 passed`; the expanded scheduler/service checks passed with `14 passed`. The complete Phase 0–7.3 regression suite passed with **461 passed and 32 warnings**. The warnings are existing UTC-naive datetime deprecations in older tests.

## Explicit boundaries and Phase 7.4 handoff

Phase 7.3 does not implement backup storage, restore verification, retention, disaster-recovery drills, or database recovery automation. Those belong to Phase 7.4. It also does not turn alerts into a second scheduler: future alert evaluation must use the same durable job contract and existing alert policy while preserving deduplication and cooldown behavior.
