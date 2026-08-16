# Phase 1.1 — Customer Registration & Start Flow

Implemented customer entry orchestration without VPN-key ownership checks.

## Flow

1. Request context middleware runs.
2. Auth middleware registers or refreshes the Telegram profile.
3. `/start` calls `CustomerEntryService`.
4. Suspended/banned accounts are restricted.
5. Users without an explicit language choice see the bilingual language selector.
6. Language selection is persisted in both user profile and user preferences.
7. `ADMIN_IDS` resolve to the admin route; ordinary users resolve to the customer route.
8. Deep-link tokens are sanitized and preserved for future referral/campaign modules.

Phase 1.2 will replace the customer placeholder route with the full customer main menu.
