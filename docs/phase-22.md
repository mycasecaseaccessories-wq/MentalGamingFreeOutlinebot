# Phase 2.2 — Wallet Payment

## Scope

Phase 2.2 implements wallet payment for an existing unpaid order. It deliberately stops after the financial/order state transition. It does not implement manual payment submission, proof uploads, wallet top-ups, refunds, VPN provisioning, Outline API calls, server selection, or key generation.

## Architecture

The handler uses `WalletPaymentService` through `ServiceRegistry`; handlers do not perform direct SQL or mutate wallet/order records. The service uses `OrderRepository`, `WalletRepository`, and `TransactionRepository` with one `DatabaseManager.session()` context. The session commits only after wallet debit, transaction ledger insertion, audit-log insertion, and order-paid update have all succeeded; any raised exception rolls the session back.

## Atomic debit flow

The payment service reloads and locks the order, verifies ownership and payability, reloads and locks the wallet, validates wallet status and currency, and checks the balance. It then executes a conditional database `UPDATE` whose predicate includes wallet identity, currency, active status, and `balance >= amount`. A successful update is followed by a negative purchase ledger row, a financial audit row, and the order payment transition. The database session commits the entire unit together.

The conditional balance predicate is intentionally retained even when a database supports `SELECT ... FOR UPDATE`; the write itself must reject a stale balance check. SQLite development uses the same conditional write while production PostgreSQL can use row locks.

## Idempotency and double-spend protection

The Phase 2.2 migration adds `transactions.order_id` and a unique `transactions.idempotency_key` index. The default wallet payment key is derived from the public order ID, and the caller may provide a bounded persistent request key. A repeated key returns the existing receipt without a second debit. A paid order with an existing ledger transaction also returns the existing receipt. Two concurrent requests against one order, and two concurrent requests against two orders sharing one wallet, are covered by real SQLite integration tests; no successful execution may make the balance negative.

## Financial invariants

A successful wallet debit has exactly one negative purchase ledger row, an order marked `Paid`, a payment reference, and a committed audit record containing order, wallet, amount, currency, and balance-before/after data. Preview is read-only. Ownership is checked on every preview and payment request. Currency mismatch, frozen wallets, expired/non-payable orders, insufficient funds, and stale balance conflicts do not debit the wallet.

## Events and failure behavior

`WALLET_DEBITED`, `ORDER_PAID`, and `WALLET_PAYMENT_COMPLETED` events are emitted only after the database session has committed. The existing EventBus suppresses and logs subscriber failures, so a post-commit subscriber failure does not reverse committed money. No success event is emitted for an idempotent replay.

## User flow

The existing order payment-method route now opens a localized wallet preview. Confirmation performs a server-side reload and calls the service. Success shows the payment reference and remaining balance. A stale confirmation returns the already-paid state without a second debit. Normal cancellation is not offered after payment; refunds are deferred.

English and Myanmar localization cover wallet payment, balance, order amount, balance after payment, confirmation, success, failure, insufficient balance, amount needed, disabled wallet, currency mismatch, payment reference, purchase, debit, and paid labels.

## Verification status

| Check | Result |
|---|---|
| Python compile check | Pass for the bot source and Phase 2.2 files |
| Fresh Alembic migration `0001 → 0009` | Pass on SQLite; new columns and unique idempotency index verified |
| Phase 2.2 real database safety tests | 8 passed |
| Phase 2.1 + Phase 1.4 + Phase 2.2 targeted regression tests | 18 passed |
| Same-order concurrent payment | Pass: one success, one ledger row, final balance 2,000 MMK |
| Two-order concurrent payment | Pass: one success, final balance 2,000 MMK, no negative balance |
| Rollback after injected post-debit failure | Pass: balance, order, and ledger restored |
| Preview no-op | Pass |
| Ownership/IDOR protection | Pass |
| Full legacy regression suite | Not claimed as passed; legacy fixture/head assertion issues remain outside the focused Phase 2.2 run |
| Lint/type-check | Not executed; no claim made |

## Deferred work

Phase 2.3 remains responsible for manual payment submission and proof upload. VPN provisioning, server assignment, Outline integration, access-key generation, refunds, and top-ups remain deferred to their designated phases.
