# Phase 6.4 — Promo Codes & Bonus Entitlements

## Scope and completion boundary

Phase 6.4 adds a data-driven Promo Code and Coupon campaign foundation. An authorized administrator can create a campaign through the `PromoService` without changing application code, configure its reward or discount, set availability and usage limits, select eligibility rules, and control its lifecycle. Customer redemption is handled by `PromoRedemptionService` and reuses the Phase 6.2 reward ledger rather than introducing a second wallet or entitlement mutation path.

Examples supported by the model and shared reward adapter include `WELCOME2026` for an extra Free Trial, `VIP1000` for a wallet credit, `BONUS1GB` for bonus data, `BONUS30D` for bonus duration, `SALE10` for a percentage discount, and fixed-value discounts. The examples are configuration data, not hard-coded campaign behavior.

The implementation deliberately does not treat a promo preview or redemption request as payment confirmation. A discount may be applied only to an owned order that is still unpaid and not cancelled, expired, completed, or refunded. Payment approval and VPN provisioning remain authoritative in their existing services.

## Domain model

`promo_codes` stores the normalized code, display-safe code, campaign name, typed promo/reward mode, amount, currency, start and expiry window, global and per-user limits, minimum purchase requirement, eligibility policy, revision, and immutable reward-policy snapshot. A unique constraint on `code_normalized` prevents ambiguous case variants.

`promo_redemptions` stores one idempotent reservation or completion record per customer request. It contains the public redemption ID, owner, optional order, state, deterministic idempotency key, reservation key, policy and eligibility snapshots, discount amount, reward reference, retry attempt count, and safe error code. Foreign keys use restrictive deletion so campaign and user history cannot be deleted underneath a redemption record.

| Area | Supported states or controls |
|---|---|
| Campaign lifecycle | Draft, scheduled, active, paused, exhausted, disabled, expired, archived |
| Reward modes | Extra Trial, Wallet Credit, Bonus Data, Bonus Duration, percentage discount, fixed discount |
| Eligibility | All active users, new users, existing users, paid users, never purchased, first purchase, role, referral, mission completer policy keys |
| Limits | Global maximum, per-user maximum, reserved count, completed count, expiry, minimum purchase, currency match |
| Redemption lifecycle | Reserved, granting, completed, failed, retrying, cancelled |

## Redemption flow

The customer supplies a code through the localized Promo Code menu. The server normalizes it to uppercase and validates its length and character set. It then reloads the campaign with a database lock, checks lifecycle and time window, checks the customer account state and configured eligibility, verifies order ownership where required, checks per-user reuse before global exhaustion, and reserves one global usage slot.

The reservation transaction commits before a reward grant is attempted. This is important because the shared Phase 6.2 reward service uses its own atomic ledger transaction. The separation prevents an uncommitted promo transaction from holding locks while the wallet or entitlement grant is being performed.

For entitlement and wallet rewards, the reward service is called with `source_type="promo"` and the redemption public ID as provenance. Extra Trial, wallet bonus, bonus data, and bonus duration therefore use the existing idempotent ledger and entitlement adapters. A retry reuses the same redemption and deterministic reward identity rather than creating a second grant.

For discounts, the service locks the owned order, refuses paid or terminal orders, calculates a capped discount, updates only the order's discount and total fields, and leaves payment status unchanged. The customer must still pass the normal payment and approval flow.

## Security and anti-abuse boundaries

Promo codes are normalized server-side, and customer callbacks do not carry reward amounts, wallet values, or arbitrary database IDs. Admin callbacks resolve public campaign IDs from the database and are protected by the existing `admin_required` boundary. Customer history is owner-scoped.

Global and per-user limits are checked from authoritative redemption rows. The in-process per-idempotency-key lock prevents same-process bursts from creating multiple logical reservations, while database uniqueness and row locks provide the durable boundary. A failed reward remains retryable and retains its original idempotency key and policy snapshot.

The implementation does not expose eligibility policy internals or sensitive account data in customer errors. Customer outcomes are generic: invalid, inactive, expired, already used, limit reached, not eligible, minimum purchase not met, or retry later. Admin views show campaign usage and lifecycle, not wallet secrets or payment credentials.

## Administration and localization

The admin handler provides a campaign list, detail view, active/paused/disabled/archive controls, usage counts, per-user limit, policy revision, and reward configuration. The service API is the authoritative creation path for creating campaigns with values such as `WELCOME2026`, `VIP1000`, `BONUS1GB`, and `SALE10`; the admin UI does not require source-code edits for new campaigns.

Customer UI includes a persistent Promo Code menu, localized entry prompt, redemption outcome, and redemption history. English and Myanmar keys cover menu labels, rewards, expired and invalid outcomes, eligibility errors, limits, and admin labels.

## Migration and verification

Migration `0031_phase64_promos` creates the two promo tables and their indexes, constraints, foreign keys, and idempotency boundaries. It follows migration `0030_phase63_missions` and does not alter or delete Phase 6.2/6.3 reward history.

The focused Phase 6.4 integration suite verifies normalization, Extra Trial fulfillment, discount application to unpaid owned orders, per-user and global limits, expiry and role eligibility, and concurrent same-key wallet redemption. The full integrated suite completed with **445 passed tests** and no failures. The remaining 32 warnings are existing datetime deprecation warnings outside the promo behavior.

## Phase 6.5 handoff

The next safe extension is operational campaign automation and richer commerce integration: scheduled expiry/exhaustion reconciliation, notification retry, admin campaign creation forms, promo analytics, explicit order-promo association in checkout presentation, refund/reversal policy, and PostgreSQL-level concurrency validation. These should extend the current reservation and reward ledger rather than bypassing it.
