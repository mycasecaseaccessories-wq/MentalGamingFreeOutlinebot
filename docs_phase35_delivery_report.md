# Phase 3.5 Delivery Report

Phase 3.5 adds a provider-neutral, read-only monitoring foundation for registered Outline servers. The implementation tracks API reachability and compatibility, management API response latency, Outline version, existing access-key count, optional metrics availability, last health check, sync attempt/success/failure timestamps, consecutive success/failure counters, safe reason codes, and stale-data state.

The design reuses the existing Outline client, credential vault, ServerORM, server-management DTOs, ServiceRegistry, event bus, and APScheduler. It does not create a second server registry or credential path. Stored credentials are decrypted only in memory for a read-only verification call; secrets and raw provider exceptions are not persisted in the operational snapshot.

Health evaluation is centralized. Optional metrics failure is treated as degraded/partial rather than immediately offline. Repeated timeout or connection-refused failures reach offline only after the configured failure threshold. Maintenance remains an explicit override while monitoring can continue. Previous successful values are marked stale when the current check fails. The sync path never creates, deletes, renames, or maps customer VPN keys and never performs routing or user reassignment; those concerns are reserved for Phase 3.6.

A Phase 3.5 migration adds sync timestamps, management API latency, safe health reason, consecutive counters, and stale-data state. The scheduler integration uses the existing APScheduler wrapper with a configurable interval, bounded max instances, coalescing, and jitter. Apply migration `0014_phase35_server_monitoring.py` before enabling scheduled synchronization in a real deployment.

Verification completed: the focused Phase 3.5 monitoring tests and the core event compatibility tests passed with **11 passed**. The full historical project suite should still be run in the target environment because unrelated legacy fixtures and migration-head expectations may require separate cleanup.
