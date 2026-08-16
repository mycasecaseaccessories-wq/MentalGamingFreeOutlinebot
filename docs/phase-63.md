# Phase 6.3 — Missions & Reward Foundation

## Scope and boundary

Phase 6.3 adds an admin-configurable Missions foundation on top of the Phase 6.2 reward engine. A mission definition describes a typed condition, target, repeat policy, availability window, business timezone, delivery mode, reward type/value, and policy revision. Mission progress is a separate per-user, per-mission, per-period read model; historical periods are retained instead of being destructively reset.

Phase 6.3 does **not** create a second wallet, reward, Free Trial, payment, provisioning, or VPN-key system. Mission rewards delegate to the existing Phase 6.2 `ReferralRewardService` entry point, which in turn reuses the existing Free Trial entitlement and wallet transaction boundaries.

## Domain model

The migration `0030_phase63_missions` adds `missions`, `user_mission_progress`, and `mission_progress_events`. It also adds nullable mission provenance fields to the Phase 6.2 reward ledger. The mission tables retain public identifiers, typed status fields, target and reward snapshots, period keys, policy revisions, timestamps, and source-event references.

| Domain | Status or invariant | Purpose |
|---|---|---|
| Mission | `draft`, `active`, `disabled`, `ended`, `archived` | Admin-controlled definition lifecycle. |
| User progress | `not_started`, `in_progress`, `completed`, `reward_pending`, `reward_granted`, `expired`, `blocked` | Separates completion from fulfillment and preserves the customer-facing state. |
| Source event | Unique user/mission/period/source reference | Prevents duplicate increments when an event is retried or delivered twice. |
| Reward | Deterministic mission/user/period provenance | Prevents duplicate reward rows across callback, worker, and process retries. |

Mission condition configuration is validated as structured data. It accepts typed event names and numeric targets, while executable code, arbitrary expressions, and unsafe evaluator fields are rejected.

## Trusted event progress

Progress is updated only by authoritative internal events. The event bridge maps qualified referrals, successful Free Trial activation, settled purchase completion, renewal completion, wallet use, and daily check-in to mission conditions. Referral clicks, pending referrals, invalid referrals, Free Trial menu opens, accepted claims, reservations, provisioning starts, pending payments, failed payments, fake proofs, and cancelled orders do not count.

Every source event is recorded before the progress increment. A duplicate logical source reference returns a duplicate result and leaves the progress value unchanged. Progress increments are bounded by the mission target and are performed in the same transaction as completion state changes.

## Repeat periods and snapshots

`ONE_TIME`, `DAILY`, `WEEKLY`, `MONTHLY`, `REPEATABLE`, and `EVENT_WINDOW` missions use a calculated period key. Daily/weekly/monthly period calculation uses the configured business timezone. A new period creates a new progress row and does not overwrite the prior period. Mission configuration and reward values are copied into progress and reward provenance snapshots so later admin edits cannot rewrite historical outcomes.

The deterministic mission reward identity is equivalent to:

```text
mission:<mission_id>:user:<user_id>:period:<period_key>
```

## Reward delivery

`AUTO_GRANT` completes the mission and immediately delegates to the shared reward service. `MANUAL_CLAIM` completes the mission as `reward_pending`; the customer callback sends only a public progress identifier, and the server reloads the authoritative row, verifies ownership and claimability, then delegates the reward. Concurrent claims and event retries resolve to one logical reward.

The supported reward foundations are Extra Trial, wallet credit, bonus data, bonus duration, and no reward. Extra Trial and bonus entitlements use existing entitlement rows. Wallet credit uses the existing bonus transaction ledger. Mission provenance is marked as `MISSION` and references the progress/period identity; mission limits are independent from referral limits unless an administrator explicitly configures shared policy.

## Admin and customer UX

The customer main menu now contains **Missions** with localized EN/MY list, detail, progress, completion, reward state, and manual claim outcomes. Customer callbacks never trust mission name, target, reward amount, period, completion, or source-event data from Telegram; only the server-resolved public progress ID is accepted.

The admin referral panel exposes an authorized Missions management entry. Admins can list definitions, inspect typed policy/revision data, and activate, disable, or archive missions by server-resolved public mission ID. Mission creation/editing remains available through the service contract with validation and revisioning; no customer-facing path can mutate definitions.

## Security and recovery

Mission event publishers are internal trusted bridges. Admin callbacks are protected by the existing admin permission decorator. Mission menu and claim paths return generic localized failures and do not expose reward ledger internals, account-risk signals, payment details, VPN secrets, or arbitrary configuration. Failed reward fulfillment remains retryable through the shared idempotent reward row; recovery never creates a second mission reward identity.

The implementation intentionally does not add device fingerprinting, promo codes, affiliate payouts, an analytics dashboard, direct wallet mutation, direct VPN-key creation, or normal Free Trial claim creation.

## Verification

Focused Phase 6.3 coverage verifies unsafe condition rejection, trusted source-event idempotency, target-bounded completion, automatic entitlement grants, manual wallet claim idempotency under concurrent calls, daily period history, and mission policy settings validation. The complete Phase 0–6.3 regression suite passes with **439 tests passed** and no failures. The remaining warnings are existing datetime deprecation warnings.

## Phase 6.4 handoff

Phase 6.4 can build Promo Codes & Bonus Entitlements on this foundation. It should reuse mission provenance and the shared reward adapter, add promo-code-specific authorization and redemption idempotency, and preserve the same completion-versus-fulfillment boundary. It should not bypass the mission/reward ledger or introduce direct balance/key mutations.
