# Phase 5 Final — Free Trial Lifecycle

## 5.1 Policy

Free Trial behavior is configuration-driven through `SettingsService`. Administrators control enablement, GB per claim, duration, device limit, normal claims per reset period, daily data cap, reset timezone, extra entitlements, paid upgrades, and server selection policy. Values are persisted and are not hardcoded in handlers.

## 5.2 Force Join

The claim gate evaluates the current configured channel/group target. Existing members pass without repeated prompts; changing the configured target causes a fresh membership check. Membership state is not treated as a permanent lifetime verification flag.

## 5.3 Claim consumption

`FreeTrialClaimService` is the atomic acceptance boundary. It locks the user and eligible entitlement rows, consumes normal or extra allowance, persists a policy snapshot, and uses idempotency plus a database uniqueness guard. Claim acceptance does not create a VPN key.

## 5.4 Server quota

`TrialServerRoutingService` filters disabled, offline, maintenance, capability-incompatible, capacity-full, and trial-quota-full servers. It atomically reserves the selected server, binds the reservation to the claim, supports fallback, and prevents the same claim or concurrent claims from consuming quota twice.

## 5.5 VPN provisioning

`FreeTrialProvisioningService` reuses the Phase 4 provisioning saga. It takes an accepted claim and committed reservation, creates one Outline key, applies the authoritative GB/device policy, verifies remote data-limit read-back, activates lifecycle expiry, binds the key to the claim, consumes the reservation, and only then makes the claim active.

> `SERVER_RESERVED != VPN_ACTIVE` and `PROVISIONING != VPN_ACTIVE`

## 5.6 Paid upgrade, conversion, abuse, monitoring, and recovery

`FreeTrialUpgradeService` supports `DATA_ADDON`, `DURATION_EXTENSION`, `DATA_AND_DURATION`, and `PAID_PLAN_CONVERSION`. It creates immutable offer snapshots and payment-pending orders. No benefit is applied before payment success. Paid orders become fulfillment-pending after payment and are fulfilled only after the Phase 4 data/lifecycle mutations complete.

Data upgrades converge the key to a target total while preserving used bytes. Duration upgrades converge to a target absolute expiry while preserving `activated_at`. Combined upgrades track each component independently, allowing safe retries after partial provider failure. Repeated payment-success events and repeated fulfillment calls have one authoritative effect.

Paid conversion changes the resulting key to the paid lifecycle and associates the target paid package while preserving the original Free Trial claim and origin. Historical trial quota is not refunded. `FreeTrialAbuseProtectionService` supports trial-specific blocks/unblocks and low-data rate limits; it does not introduce invasive fingerprinting. `FreeTrialAnalyticsService` provides read-only admin aggregates, and pending fulfillment recovery is idempotent.

EN/MY outcomes distinguish payment pending, payment received/processing, upgrade success, provider failure, delayed provisioning, trial restriction, and final VPN readiness. Notification failure cannot change fulfillment state.

## Final invariants

| Boundary | Required distinction |
|---|---|
| Server reservation | `SERVER_RESERVED != VPN_ACTIVE` |
| Provisioning | `PROVISIONING != VPN_ACTIVE` |
| Payment | `PAYMENT_PENDING != PAYMENT_SUCCESS` |
| Fulfillment | `PAYMENT_SUCCESS != UPGRADE_FULFILLED` |
| User messaging | UX text is not the source of truth |
| Security | Customer input cannot forge price, currency, limits, payment, fulfillment, or ownership |

## Verification status

The Phase 5.6 focused tests pass. The full clean Phase 0–5.6 regression suite passes with the Alembic head `0026_phase56_paid_trial_upgrade`. Phase 5.6 should be marked complete only against that validated source tree and migration head.
