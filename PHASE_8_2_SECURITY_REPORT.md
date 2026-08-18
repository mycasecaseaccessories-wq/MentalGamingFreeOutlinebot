# Phase 8.2 — Telegram Callback & Request Security Report

## Final verdict

**SECURE_WITH_WARNINGS**

The Phase 8.2 callback-security requirements are implemented and the executable verification gates pass. The verdict is `SECURE_WITH_WARNINGS` rather than `SECURE` because the working tree contains uncommitted Phase 8.2 changes and the verified commit has not been pushed after these changes.

## Implemented controls

The bot now uses durable `cb2:<public_id>:<token>` callback references backed by `CallbackActionORM` and `CallbackRateLimitORM` in migration `0041_phase82_callback_security`. References are actor-bound, Telegram-account-bound, chat-bound where applicable, resource-bound, expiring, single-use, and protected by row locking for replay/double-submit resistance.

The secure callback path covers admin payment review, customer order checkout/payment/cancel, customer mission claim, Free Trial claim, admin server controls, Outline provisioning confirmation/review actions, and customer-key Free Trial entry. Legacy raw mutation callbacks are rejected or retained only as safe compatibility fallbacks; read-only navigation remains backward-compatible.

## Evidence

| Check | Result |
|---|---:|
| Focused Phase 8.2 tests | **3 passed** |
| Full Phase 0–8.2 regression suite | **496 passed, 32 warnings** |
| Python compile check | **Passed** |
| `git diff --check` | **Passed** |
| Unsafe privileged-grant source audit | **UNSAFE match = 0** |
| Migration head | **0041_phase82_callback_security** |
| Phase 8.3 started | **No** |

The full suite initially exposed three stale test expectations for the Phase 8.1 migration head. Those assertions were updated to the actual Phase 8.2 head, after which all 496 tests passed.

## Git verification

The local commit and `origin/main` were both `a7c75fe8f057351c50dc1b0a32026787468281b5` before the current Phase 8.2 changes. The current working tree contains the Phase 8.2 modifications and is not clean. Therefore, no claim is made that these changes are committed or pushed.

## Warnings and follow-up

The regression suite reports 32 existing deprecation warnings related to `datetime.utcnow()` usage. They are non-blocking for Phase 8.2 but should be addressed in a later maintenance pass. The Phase 8.2 changes should be committed and pushed only after the user confirms the final diff, or according to the project’s normal release workflow.

Phase 8.3 should not begin until the current Phase 8.2 changes are committed/pushed if repository synchronization is required by the release gate.
