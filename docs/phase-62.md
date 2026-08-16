# Phase 6.2 — Referral Qualification and Rewards

Phase 6.2 turns Phase 6.1 attribution into a durable qualification and reward workflow. A Telegram deep-link click creates only a `pending_qualification` referral. A referral becomes qualified only after server-observed policy requirements pass, and rewards are issued only from an idempotent reward ledger.

## Qualification architecture

`ReferralQualificationService` evaluates the authoritative referral row and referred-user row. It uses `UserORM.first_seen_at`, which is the first server-observed bot interaction and is not Telegram account creation time. The service never estimates Telegram account age from user IDs or undocumented metadata. The attribution timestamp, configured waiting period, current Force Join verification, authoritative Free Trial provisioning state, and optional paid order state are evaluated from database-backed business records.

The persisted states distinguish `pending_age_requirement`, `pending_wait_period`, `pending_force_join`, `pending_free_trial_activation`, `pending_paid_purchase`, `review_required`, `qualified`, and `invalid`. A referral under review remains a valid relationship and is not silently converted to invalid. Re-evaluating a referral is safe and does not create duplicate rewards.

## Admin policy

All material rules are SettingsService values. The settings registry contains minimum first-seen age, qualification wait, Force Join, Free Trial activation, paid purchase, burst detection, suspicious review, reward mode, required qualified count, reward types and values, daily/weekly/monthly/lifetime limits, cooldown, expiry, and wallet currency. Settings must be non-negative and reward values must match supported reward types before being exposed through an admin form.

| Policy area | Canonical settings |
|---|---|
| Qualification | `referral_min_first_seen_age_seconds`, `referral_qualification_wait_seconds`, `referral_require_force_join`, `referral_require_free_trial_activation`, `referral_require_paid_purchase` |
| Risk/review | `referral_burst_detection_enabled`, `referral_burst_threshold`, `referral_burst_window_seconds`, `referral_review_suspicious` |
| Reward cycle | `referral_reward_mode`, `referral_required_qualified_count`, `referral_referrer_reward_*`, `referral_referred_reward_*` |
| Limits | `referral_reward_daily_limit`, `referral_reward_weekly_limit`, `referral_reward_monthly_limit`, `referral_reward_lifetime_limit`, `referral_reward_cooldown_seconds` |
| Fulfillment | `referral_reward_expiry_seconds`, `referral_reward_wallet_currency` |

## Reward ledger and integrity

`ReferralRewardORM` stores one row per referral, beneficiary, and reward cycle. Referrer and referred-user rewards are never combined into one ambiguous mutation. The deterministic key `referral_reward:<policy revision>:<referral id>:<beneficiary>:<cycle>` and the database uniqueness constraints prevent duplicate grants across repeated qualification events, worker retries, restarts, admin retries, and double-clicks.

Reward fulfillment is separate from qualification. Extra Trial rewards create `FreeTrialEntitlementORM` rows and do not create VPN keys directly. Wallet rewards update the beneficiary wallet and append a `TransactionORM.TYPE_BONUS` ledger entry with the same idempotency key inside one database transaction. Existing successful rewards are never undone when a separate beneficiary reward fails; failed rows remain retryable.

Daily, weekly, monthly, lifetime, and cooldown checks are evaluated per beneficiary. A reward that reaches a limit is stored as `limit_reached`; the referral remains qualified and historical attribution is preserved. The unique reward-cycle constraint and transaction/row-lock path provide the database boundary needed for concurrent processing.

## Abuse protection and privacy

`ReferralRiskEventORM` records durable attribution events with a safe idempotency key and no invasive identifiers. Configured burst velocity can move a referral to `review_required`. Customer messaging is generic and does not expose risk scores, exact thresholds, other users' activity, VPN access URLs, wallet secrets, or payment secrets. Phase 6.2 does not collect IMEI, MAC addresses, contacts, browser/device fingerprints, unnecessary IP profiles, or fabricated Telegram account-age data.

## Review and recovery

The admin referral panel exposes a suspicious-referral queue and authorized approve/reject/keep-pending actions keyed by server-resolved public referral IDs. Approval returns the referral to the same qualified-event reward bridge; rejection invalidates it with an admin reason. Reward history is read from the ledger. Notifications are downstream of the grant boundary and must not change a `granted` row back to failed.

## Localization and handoff

English and Myanmar strings cover pending age/wait/action states, under review, qualified, reward pending/granted, reward limits, progress, Extra Free Trial, wallet, bonus data, bonus duration, anti-abuse settings, suspicious referrals, review status, and reward history. Phase 6.3 may add scheduled rechecks and notification retry workers; it must preserve the current qualification state machine, immutable first attribution, reward idempotency, and ledger boundaries.

## Verification scope

The focused Phase 6.2 suite covers server-observed first-seen age, wait-period recheck idempotency, self-referral invalidation, burst review, separate referrer/referred Extra Trial rewards, and wallet bonus ledger idempotency. Full regression must run with the new migration head `0029_phase62_referral_rewards` and must not mark any Phase 6.3 or later scope complete.
