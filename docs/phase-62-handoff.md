# Phase 6.2 Handoff — Referral Qualification and Rewards

Phase 6.1 leaves every valid referral in `pending_qualification`. The next phase may add qualification rules, but it must not infer qualification merely from link attribution.

## Allowed next-phase extensions

Phase 6.2 may define qualifying actions, qualification windows, idempotent qualification records, reward policy snapshots, and reward-grant events. It may consume `ReferralQualificationService.evaluate()` as the extension point.

## Boundaries to preserve

The first valid referrer remains immutable. Self-referral and invalid-token protections remain active. Existing-user `/start` payloads must not create new attribution. Rewards must be issued only after a durable qualification decision and must have their own idempotency key. Customer history must remain privacy-safe, and administrative invalidation must remain auditable.

Phase 6.2 must not silently add payment conversion, commissions, payouts, or wallet mutations without a separate approved specification and migration/test plan.
