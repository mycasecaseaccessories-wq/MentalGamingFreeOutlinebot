# Phase 6.5 — Anti-Fraud Analytics & Referral Intelligence

## Scope and design boundary

Phase 6.5 adds operational visibility and privacy-safe risk monitoring to the referral system without replacing the authoritative Phase 6.1–6.4 state machines. Analytics are read-only aggregations over referrals, rewards, orders, promo redemptions, and durable risk observations. Risk actions are explicit Admin mutations and are audited.

The implementation deliberately uses **server-observed business data only**. It does not infer Telegram account creation time and does not collect device fingerprints, IMEI, MAC addresses, contact lists, invasive IP profiles, or hidden client identifiers. `first_seen_at` remains the application’s first-observed timestamp and is used only as one weak signal in a combined decision.

## Analytics

`ReferralAnalyticsService` exposes bounded period-aware methods for the Admin layer. Supported periods include today, yesterday, the last seven days, the last thirty days, this month, the previous month, all time, and explicit UTC ranges. Configured business timezone is used to determine calendar boundaries while persisted timestamps remain UTC-aware.

| Area | Implemented output |
|---|---|
| Overview | Attributed, qualified, pending, invalid, under-review, granted rewards, and paid conversions |
| Funnel | Attributed → registered → Force Join complete → Free Trial activated → qualified → reward eligible → reward granted |
| Conversion | Attribution-to-qualification and qualification-to-reward percentages with zero-denominator protection |
| Rewards | Counts and values grouped by source and reward type, with granted, failed, held, and limit-reached states kept separate |
| Referrers | Bounded top-referrer ranking by attribution, qualification, paid conversion, or granted reward |
| Qualification | State distribution for the selected time range |
| Limits and risk | Reward-limit hit counts and durable risk-observation summaries by signal, level, and action |
| Growth | Daily attributed, qualified, invalid, and review-required time-series points |
| Campaigns | Promo redemption, completed, and failed counts by campaign |
| User view | Admin-only per-user referral and reward summary without exposing internal scores to customers |

Reward units are not collapsed into an invented monetary valuation. Extra trials, data, duration, wallet credit, discounts, and other reward types retain their original type and value, which avoids misleading comparisons across reward currencies.

## Risk monitoring

`ReferralRiskService` evaluates velocity and behavioral signals against Admin-configurable policy values. The current signal vocabulary includes referral velocity, qualification velocity, reward velocity, invalid-attempt velocity, short first-seen age, rapid-trial patterns, reward-limit hits, repeated review history, and self-referral/duplicate-attribution categories reserved for trusted event producers.

A single weak signal does not prove fraud. The combined evaluator raises a review recommendation when multiple independent velocity dimensions cross their thresholds. The default safety posture is observation plus review/hold rather than global account destruction. Automatic feature-scoped blocking is disabled by default and can be enabled only as an explicit policy choice.

| Risk action | Meaning | Customer-impact boundary |
|---|---|---|
| Observe | Store a durable signal for later analysis | No access or reward mutation |
| Review Required | Put the referral case in the Admin queue | Does not globally ban the user |
| Hold Reward | Keep a referral reward in `review_required` | Existing paid VPN access remains unaffected |
| Referral Reward Block | Disable only new referral reward grants for one user | Paid VPN, existing keys, wallet, orders, and normal access remain available |
| Release Held Reward | Retry the existing reward row through the idempotent reward engine | No duplicate reward row or double grant |

Observations are deduplicated by a stable user/signal/date/policy-revision key and retain only safe metadata such as a count, threshold, source event type, and policy revision. Review mutations store the Admin actor, resolution, note, and timestamp in both the risk observation and the audit log.

## Reward integration

The shared `ReferralRewardService` now checks the beneficiary’s referral-only block state before granting a referral reward. A blocked referral reward is persisted as `review_required` with `limit_result=referral_reward_blocked` and `risk_result=blocked`; it is not silently discarded. Mission and promo reward sources are not blocked by this flag.

Admin release calls `release_held_reward()`, which reuses the deterministic idempotency key and existing grant transaction. A granted row is returned as already terminal; a held row is retried only once through the established engine. This preserves the Phase 2.2/6.2 atomicity and double-spend protections.

## Admin UX

The existing Admin Referrals screen now contains separate entries for **Referral Analytics** and **Risk Review Queue**. Analytics show the last-thirty-day overview and funnel in a compact localized view. The risk queue is paginated at the service boundary and displays the observation identifier, affected user, signal, risk level, and action.

Review callbacks support approve, reject, keep pending, release held reward, block referral rewards, and unblock referral rewards. All callbacks pass through the existing `admin_required` guard and use compact, non-secret callback data. No password, API credential, device identifier, internal risk score, or raw sensitive evidence is shown to customers.

## Localization

English and Myanmar translations cover the new Admin analytics labels, funnel and conversion terms, risk queue states, review actions, and customer-safe outcome messages. Customer messages intentionally describe operational outcomes—such as a held referral reward—without exposing thresholds, internal scores, or detection logic.

## Schema and integration

Migration `0032_phase65_referral_analytics` adds the durable risk-observation and supporting referral-risk structures, along with the Phase 6.5 user feature-scoped referral reward block fields. The ServiceRegistry registers analytics and risk services after referral and reward dependencies are available. Trusted referral, reward, mission, promo, and order events invoke risk evaluation through a low-priority bridge so primary business transactions remain authoritative.

## Validation evidence

The focused Phase 6.5 integration module covers Admin authorization and funnel aggregation, deduplicated velocity observations, review candidate access, and feature-scoped referral reward holds. The full repository regression suite completed with **448 passed tests and 32 deprecation warnings** using disposable test credentials and the configured test Admin ID. No test failures remained after updating legacy migration-head assertions from Phase 6.4 to the integrated Phase 6.5 revision.

## Phase 6.6 handoff

Phase 6.6 should be limited to final integration hardening: verify production settings are seeded with the intended thresholds, verify event payload contracts in the running Telegram application, add any deployment-specific operational dashboards or alert routing, test concurrent Admin callbacks against the production database engine, and perform a final privacy/security review. It should not introduce a new reward source, global ban mechanism, invasive identity signal, or a second analytics source of truth.
