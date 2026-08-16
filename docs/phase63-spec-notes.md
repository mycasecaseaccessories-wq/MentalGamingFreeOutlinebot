# Phase 6.3 Specification Notes

Source: `/home/ubuntu/upload/Pasted_content_35.txt` supplied by the user.

Phase 6.3 implements Missions & Reward Foundation only. It must reuse the Phase 6.2 reward/entitlement architecture and must not create a second reward engine, directly mutate wallet balances, directly create VPN keys, or directly create normal Free Trial claims.

The mission domain requires admin-managed definitions with public ID, typed mission type, validated condition configuration, reward policy/reference, repeat mode, target, availability window, cooldown/reset, business timezone, enabled/status, sort order, and revision-aware snapshots. Condition configuration must never contain executable code or arbitrary expressions.

Mission configuration statuses are DRAFT, ACTIVE, DISABLED, ENDED, and ARCHIVED. User progress statuses are NOT_STARTED, IN_PROGRESS, COMPLETED, REWARD_PENDING, REWARD_GRANTED, EXPIRED, and BLOCKED. Progress is a separate per-user/per-mission/per-period read model with target and reward snapshots, period key, policy revision, timestamps, and reward reference.

Supported foundations include JOIN_CHANNEL, QUALIFIED_REFERRAL_COUNT, FREE_TRIAL_ACTIVATED, FIRST_PAID_PURCHASE, PAID_PURCHASE_COUNT, PURCHASE_AMOUNT, VPN_RENEWAL, DAILY_CHECK_IN, WALLET_USAGE, and trusted CUSTOM_EVENT. Repeat modes include ONE_TIME, DAILY, WEEKLY, MONTHLY, REPEATABLE, and EVENT_WINDOW. Period-based progress must be used instead of destructive reset jobs, preserving historical auditability and configured business timezone.

Progress must be driven by trusted authoritative business events. Qualified referral missions count only Phase 6.2 qualified referrals, not clicks, shared links, pending, or invalid referrals. Free Trial missions count only successful ACTIVE/provisioned activation, not menu open, eligibility, accepted claim, reservation, or provisioning start. Purchase missions count only authoritative successful settled/completed orders, not pending, failed, fake proof, or cancelled orders. Duplicate source events must not increment twice; a source-event ledger with a unique logical reference is expected.

Completion must be separated from reward fulfillment. AUTO_GRANT creates a deterministic mission-period reward record and delegates to the shared reward engine. MANUAL_CLAIM sets REWARD_PENDING and reloads authoritative progress before allowing a claim. The deterministic identity should be equivalent to `mission:<mission_id>:user:<user_id>:period:<period_key>`. Concurrent claim clicks and event retries must result in one reward only.

Rewards may be EXTRA_FREE_TRIAL, WALLET_CREDIT, BONUS_DATA, BONUS_DURATION, PROMO_ENTITLEMENT, or NONE. Extra Trial must reuse FreeTrialEntitlement, wallet rewards must use WalletService/ledger, and bonus data/duration must reuse the existing Phase 6.2 entitlement foundation. Mission reward provenance must be MISSION plus a safe mission-progress/period reference. Referral-specific reward limits must not unintentionally block unrelated mission rewards unless explicitly configured.

Admin UX needs mission menu, create/edit/review/activate/disable/archive, typed condition/reward configuration, availability windows, reward delivery mode, stats, progress inspection, manual-complete support with permission/audit, safe retry, and non-destructive historical behavior. Customer UX needs Missions, available mission list, detail/progress, contextual CTA, completed mission history, reward state, and claim action. Customer callbacks cannot forge mission ID ownership, progress, target, reward amount/type, completion, period, or source event.

Security requirements include centralized permissions, account restrictions, rate limits for menu refresh/claim/check-in, no invasive device fingerprinting, trusted internal event publishers only, safe logging without VPN/payment secrets, and audit events for mission lifecycle/manual completion/reward retry. Phase 6.3 must not implement promo codes, affiliate payouts, a new wallet/reward/provisioning/Free Trial system, or Phase 6.5 analytics/anti-abuse dashboard.

Required tests include mission config validation and permissions; referral, Force Join, Free Trial activation, purchase, renewal, daily check-in; AUTO_GRANT and MANUAL_CLAIM; reward idempotency; source-event idempotency; concurrency/no lost updates/no target overshoot; snapshot/revision behavior; security/forged callbacks; migration and full Phase 0–6.2 regression. Completion must document Phase 6.4 readiness for Promo Codes & Bonus Entitlements.
