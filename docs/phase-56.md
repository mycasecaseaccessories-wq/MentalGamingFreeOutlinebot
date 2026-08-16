# Phase 5.6 — Paid Free Trial Upgrade and Conversion

Phase 5.6 extends the existing Phase 4 provisioning and Phase 2 order/payment boundaries. Telegram handlers do not call Outline directly, mutate the wallet directly, or treat messages as authoritative state. The service boundary is `FreeTrialUpgradeService`.

## Upgrade offers

Administrators publish immutable offers using `FreeTrialUpgradeOfferORM`. Supported types are `DATA_ADDON`, `DURATION_EXTENSION`, `DATA_AND_DURATION`, and `PAID_PLAN_CONVERSION`. The offer price, currency, byte delta, duration delta, target package, enabled state, and purchase limit are snapshotted into `FreeTrialUpgradeORM` when an order is created.

## Payment and fulfillment

Creating an upgrade order produces `PAYMENT_PENDING` / `waiting_payment` and creates no benefit. Existing wallet or manual-payment services may transition the order to `PAYMENT_PAID`; fulfillment then moves the upgrade to `FULFILLMENT_PENDING`. Only after authoritative provider and lifecycle mutations succeed does the upgrade become `FULFILLED` and the order become `COMPLETED`.

> `PAYMENT_PENDING != PAYMENT_SUCCESS != UPGRADE_FULFILLED`

The data component converges the key to an absolute target byte limit through `VPNDataLimitService`, preserving the existing used-byte value. The duration component converges the key to an absolute target expiry through `VPNLifecycleService.extend_key_to`, preserving `activated_at`. A repeated fulfillment event sees the fulfilled row and has no second effect. Combined upgrades retain component flags so a retry only attempts unfinished work.

## Paid plan conversion

Paid conversion is a paid upgrade type. After fulfillment, the same VPN key changes from the Free Trial key type to `paid`, receives the target package reference, and the original claim remains intact with its `FREE_TRIAL` origin/source. Historical trial server quota is not refunded.

## Admin policy and server quota

The canonical policy keys are seeded in `config/defaults.py`: enablement, data per claim, duration, device limit, claims per period, daily data cap, reset timezone, extra entitlements, paid-upgrade enablement, server selection mode, and action velocity. Phase 5.4 remains the reservation authority for per-server trial quota and fallback. `SettingsService` is the persistence boundary for policy changes.

## Abuse, monitoring, and recovery

`FreeTrialAbuseProtectionService` provides account-state checks, trial-specific blocks/unblocks, and low-data action rate limiting without invasive fingerprinting. Velocity counters are persisted in `free_trial_rate_limits` with a unique `(user_id, action)` key and row-locked updates, so separate workers share one enforcement boundary. The configured window is read from `SettingsService`. `FreeTrialAnalyticsService` exposes read-only admin totals for claims, reservations, active trials, upgrade states, revenue, conversions, and blocked users. `recover_pending_fulfillment` retries paid-but-unfulfilled upgrades idempotently; provider failure leaves payment successful and fulfillment pending for retry.

## Localization and UX boundaries

EN and MY include explicit messages for server preparation, ready state, payment pending, payment received/processing, upgrade success, upgrade failure, conversion, restrictions, and rate limits. `SERVER_RESERVED`, `PROVISIONING`, and `VPN_ACTIVE` remain separate states. A reserved or provisioning claim must never show a VPN-ready message.

## Security invariants

Customer-supplied values cannot override offer price, currency, bytes, duration, devices, server quota, payment status, or fulfillment. All upgrade lookups are ownership checked. Restriction changes require an active admin. Migration `0027_phase56_integrity_and_rate_limits` enforces foreign keys for users, keys, claims, offers, packages, orders, and rate-limit rows. Public identifiers and idempotency keys are used in the order boundary; secrets and access URLs are not included in upgrade events.

## Validation

The Phase 5.6 focused suite covers idempotent order creation, payment gating, additive data application, used-byte preservation, duration extension, paid conversion provenance, trial-specific abuse restrictions, and durable rate-limit behavior. The complete repository regression suite passes with the hardened migration head `0027_phase56_integrity_and_rate_limits`.
