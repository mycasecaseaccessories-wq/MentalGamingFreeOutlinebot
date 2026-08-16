# Phase 5.3 Delivery Report — Atomic Free VPN Claim Acceptance

Phase 5.3 changes the Free VPN button from a placeholder/read-only screen into an acceptance boundary. The handler now calls `FreeTrialClaimService` and the service performs authoritative eligibility revalidation, current target membership verification when the service is supplied, account-state checks, and claim acceptance before any future VPN provisioning phase. **No Outline key is created in Phase 5.3.**

The transaction locks the user row with `SELECT ... FOR UPDATE` on databases that support row locks. SQLite remains serialized by its write transaction behavior. Idempotency is enforced by the unique `idempotency_key`; a retry with the same key returns the original claim rather than consuming another allowance. A conflicting `accepted`, `queued`, or `provisioning` claim is rejected. Normal daily claims are selected before extra entitlements. The service counts accepted normal claims and granted bytes for the current UTC reset period and refuses partial claims when the remaining cap is below one full claim.

Extra entitlements are stored separately with `remaining_uses`. The selected entitlement row is locked, one use is decremented in the same transaction that inserts the accepted claim, and custom entitlement data/duration/device values are snapshotted. `cancel_claim()` provides the failure-compensation boundary: an extra entitlement use is restored when cancellation occurs before the entitlement is delivered, while normal daily claim release/refund policy remains an explicit later orchestration decision.

The claim record stores `source`, `period_start`, `status`, `data_limit_bytes`, `duration_seconds`, `device_limit`, `policy_snapshot_json`, acceptance timestamps, and cancellation metadata. Migration `0023_phase53_atomic_free_trial_claims.py` creates the entitlement table, removes the old one-claim-per-user constraint, backfills legacy claim rows conservatively, and adds the new fields.

The customer callback has bilingual EN/MY outcomes for acceptance, daily exhaustion, missing extra entitlement, membership requirement, and temporary disablement. Registry wiring creates one shared `FreeTrialClaimService` instance. The existing full migration test run is currently blocked by an inherited repository issue: `0021_phase51_free_trial_claims.py` references `0020_phase46_recovery_rotation`, but that revision file is absent from the supplied source tree. Python compilation for the Phase 5.3 changed modules passes. Full SQLite concurrency assertions should be rerun after the missing migration-chain revision is restored.

## Phase 5.4 handoff

Phase 5.4 should consume `ACCEPTED` claims for server quota/routing without moving them to `ACTIVE`, transition claims through `QUEUED` and `PROVISIONING`, and invoke `cancel_claim()` only for infrastructure failures covered by the compensation policy. It must not create a second allowance-consumption path.
