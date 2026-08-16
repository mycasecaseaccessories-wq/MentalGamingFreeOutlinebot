# Phase 6.1 — Referral Core and Invite Tracking

## Scope

Phase 6.1 establishes referral identity and attribution only. It does **not** grant rewards, calculate commissions, convert referrals into paid plans, or implement payouts. Those behaviors remain explicit Phase 6.2+ extension points.

## Core flow

1. A registered user requests a personal referral link.
2. `ReferralTokenService` creates or reloads one stable, unique token per user.
3. The bot username is resolved at runtime and the link is built as `https://t.me/<bot>?start=ref_<token>`.
4. The `/start` handler parses the generic payload namespace safely.
5. After the existing user-registration boundary has completed, `ReferralService.attribute_from_start()` accepts only a valid `ref_` payload for a genuinely new user.
6. The referral relationship is inserted with `pending_qualification` status and no reward or commission side effect.

## Invariants

| Invariant | Enforcement |
|---|---|
| One stable token per user | `referral_tokens.user_id` unique constraint |
| One token value maps to one user | `referral_tokens.token` unique constraint |
| First valid attribution wins | `referrals.referred_id` unique index plus transaction/IntegrityError recovery |
| Self-referral is rejected | Service-level referrer/referred identity check |
| Existing users are not attributed | `require_new_user` policy and registration state |
| Invalid payloads do not block onboarding | Parser returns safe non-referral outcomes and `/start` catches attribution failures |
| No rewards in Phase 6.1 | Qualification service returns pending state only; no reward event exists |
| Admin actions are authorized | Existing `admin_required` decorator and actor validation in service |
| Private history is privacy-safe | Customer history exposes labels, status, and public referral IDs only; no Telegram IDs or usernames |

## Persistence

Migration `0028_phase61_referral_core` adds the `referral_tokens` table and evolves the legacy `referrals` table with public IDs, token provenance, source, attribution metadata, status timestamps, invalidation fields, foreign keys, and the unique primary-referrer boundary. Existing legacy rows are backfilled with deterministic public IDs and `personal_link` source values.

## UX and controls

Customers receive a localized **Refer Friends** menu entry with their personal link, share action, aggregate counts, and privacy-safe referral history. Administrators receive authorized referral statistics, recent referral listing, referral enable/disable controls, and invalidation foundation callbacks. All callback payloads use explicit `ref:` or `admin:ref:` namespaces.

## Localization

English and Myanmar dictionaries contain referral menu labels, link instructions, status labels, invalid-link and self-referral outcomes, admin controls, and safe generic errors.

## Phase 6.2 handoff

`ReferralQualificationService.evaluate()` is deliberately a reward-free extension point returning `pending_qualification`. Phase 6.2 may add qualification rules, but must preserve the Phase 6.1 attribution row, idempotency, privacy, and no-reward-before-qualification boundaries.

## Verification

The Phase 6.1-focused referral suite covers token stability, token format, runtime link generation, payload parsing, valid attribution, pending status, no commission side effect, self-referral rejection, invalid-token safety, existing-user protection, first-attribution behavior, and concurrent one-primary-referrer enforcement. The complete Phase 0–6.1 regression suite passes with **421 tests passed**.
