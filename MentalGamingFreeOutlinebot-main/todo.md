# Telegram Bot Delivery Checklist

- [x] Verify the integrated Phase 0–1.5 handler, service, and migration wiring in the main bot source.
- [x] Confirm P0 middleware ordering and restricted-account dispatch stopping are implemented correctly.
- [x] Add the PostgreSQL async driver and make the database environment-variable contract consistent.
- [x] Validate syntax, dependency manifests, and targeted regression tests where available.
- [x] Package a clean run-ready Telegram bot ZIP with concise setup guidance.

## Phase 2.1 — Order Creation & Checkout Foundation

- [x] Inspect existing Order-related models, tables, enums, repositories, services, DTOs, and migrations before adding anything.
- [x] Implement checkout confirmation with package revalidation and stale-price/attribute protection.
- [x] Implement order creation with public order ID, package/price snapshots, expiry, and ownership-safe persistence.
- [x] Add centralized order and payment state transition validation without implementing payment or VPN provisioning.
- [x] Add idempotent checkout confirmation, duplicate-order prevention, and customer cancellation flow.
- [x] Add payment-method handoff placeholders only; do not move money or generate VPN keys.
- [x] Add Phase 2.1 migrations and regression tests, then validate the bot source and package a Phase 2.1 archive.

## Phase 2.2 — Wallet Payment & Atomic Balance Deduction

- [x] Inspect existing Wallet, Transaction, Order, Result/error, event, registry, migration, and test architecture before changes.
- [x] Reuse existing Wallet and Transaction models/repositories without creating duplicates.
- [x] Implement wallet-payment preview without mutating balance or order state.
- [x] Implement one database transaction covering order validation, wallet validation, debit, transaction creation, payment reference, and order state updates.
- [x] Add idempotency for repeated callbacks and already-paid orders.
- [x] Add row locking/concurrency protection and prove concurrent attempts cannot double-spend.
- [x] Enforce ownership, currency, wallet status, expiry, exact-balance, and insufficient-balance rules.
- [x] Ensure rollback restores wallet, transaction, and order state when any step fails.
- [x] Do not implement manual payment, top-up, VPN provisioning, key generation, or server selection in Phase 2.2.
- [x] Add migration, localized wallet-payment flow, focused tests, and evidence for atomicity/idempotency/double-spend protection.
- [x] Package the Phase 2.2 bot archive only after all focused tests pass.

## Phase 2.3 — Manual Payment Submission & Proof Upload

- [x] Inspect existing payment/submission models, enums, upload/file handling, settings, events, admin notifications, and tests before adding anything.
- [x] Reuse or safely extend existing payment/order infrastructure without creating duplicate payment, upload, transaction, or notification systems.
- [x] Add configurable enabled manual payment methods and customer-safe public instructions without exposing secrets.
- [x] Implement manual payment method selection and instruction flow with safe compact callbacks.
- [x] Implement reference/proof submission with ownership, order-state, expiry, currency, amount, and duplicate/idempotency validation.
- [x] Persist proof metadata only; keep the order awaiting review and never mark it Paid on submission.
- [x] Notify admins without making notification delivery part of the financial commit boundary.
- [x] Ensure screenshot/reference submission cannot generate VPN keys or call provisioning.
- [x] Add English/Myanmar localization for manual payment and Pending Review states.
- [x] Add migration and focused tests for Pending Review, duplicate/fake proof, IDOR, expiry, already-paid, upload metadata, and Paid-boundary protection.
- [x] Package Phase 2.3 only after focused tests and boundary verification pass.

## Phase 2.4 — Admin Payment Approval, Rejection & Review Workflow

- [x] Inspect existing admin architecture, permissions, payment submission/order services, notification provider, event bus, audit logging, migrations, and tests.
- [x] Define and implement one-terminal-decision concurrency boundary for double-click and concurrent-admin approval/rejection.
- [x] Add admin-only pending payment queue with newest-first pagination and review details.
- [x] Add secure authorized-admin proof viewing without public proof URLs or leakage to logs/exports.
- [x] Implement approval confirmation and atomic approval transition to submission Approved + order Paid, without VPN key generation or Outline API calls.
- [x] Implement rejection confirmation/reason capture and atomic rejection transition without changing the order to Paid.
- [x] Add customer/admin notifications and audit records without making external delivery part of the financial commit boundary.
- [x] Add bilingual Phase 2.4 localization and integrate with the existing Admin Panel.
- [x] Add migrations and focused tests for concurrent approval, double-click idempotency, approve-vs-reject race, unauthorized access, forged callbacks, stale/invalid orders, proof privacy, notifications, audit trail, and no-provisioning boundary.
- [x] Package and verify the Phase 2.4 ZIP archive and delivery report.

## Phase 2.5 — Customer Order History, Payment History & Phase 2 Completion

- [x] Inspect current Order, WalletTransaction, PaymentSubmission, customer navigation, pagination, localization, RequestContext, ownership checks, and tests.
- [x] Implement read-only customer order history from authoritative orders with snapshot display, newest-first pagination, filters where supported, and ownership-safe details.
- [x] Implement read-only normalized payment history by merging wallet transactions, manual submissions, and order payment fields without creating duplicate history tables.
- [x] Implement customer-safe wallet transaction history and manual submission history with references, statuses, rejection reasons, and dates.
- [x] Add bilingual customer navigation, localized history/detail/empty/error messages, and maintain backward compatibility.
- [x] Add Phase 2.5 focused ownership, IDOR, read-only, pagination, snapshot, status, and Phase 0–2.4 regression tests.
- [x] Mark Phase 2 complete after all Phase 2.5 tests pass.
- [x] Build and verify one clean master ZIP containing the complete Phase 0 through Phase 2.5 source tree, not separate phase-only code archives.
- [x] Prepare the Phase 2 completion report and Phase 3 server-management starting scope.

## Phase 3 — Server Management & Provisioning Foundation

- [ ] Inspect existing server/VPN/provider abstractions, secrets handling, admin permissions, health checks, sync jobs, and tests before implementation.
- [ ] Add admin-only Servers menu with Add Server, Server List, detail/edit, and maintenance controls.
- [ ] Add secure API URL and SSH configuration handling without exposing credentials in logs, customer UI, or archives.
- [ ] Define Auto Provision eligibility separately from Phase 2 payment approval.
- [ ] Implement server health, sync, load-balance, and maintenance state boundaries with focused tests.

## Phase 3.1 — Server Domain, Registry & Admin Management Foundation

- [x] Inspect existing server model/repository/service/filters/DTOs, provider registry/contracts, plugin architecture, ServiceRegistry, Admin Panel, permissions, RequestContext, Result/Event/Hook/audit/settings/cache/pagination/localization/validators/migrations/tests/docs.
- [x] Define the revised server lifecycle so manual registration defaults to `health_status=unknown`, `status=unknown`, and `enabled=false`; never infer Online/Enabled from metadata-only creation.
- [x] Reuse or minimally extend the authoritative server schema with immutable public identifier, validated metadata, provider/integration type, capacity/load fields, maintenance/archive state, and future-safe references.
- [x] Implement server repository/service/policy validation and admin-only mutations for manual registration, edit, enable/disable, maintenance, and archive.
- [x] Wire ServerRegistry, events/hooks/audit records, and ServiceRegistry without implementing real Outline/SSH/Auto Provision connectivity.
- [x] Integrate existing Admin Panel with Servers, Add Server method choices, Server List, detail, status/capacity, maintenance, and guarded future routes.
- [x] Add English/Myanmar localization and prevent secrets/API URLs/SSH material from customer UI, logs, or unsafe output.
- [x] Add focused tests for default Unknown+Disabled state, validation, authorization, public ID safety, lifecycle transitions, archive behavior, concurrency/idempotency, audit/events, and future-route non-success.
- [x] Verify Phase 3.1 and package the integrated Phase 3.1 deliverable.

## Phase 3.2 — Outline Setup Core

- [x] Inspect Phase 3.1 server/admin/provider/client/network/secret/settings/event/audit/result/cache/localization/migration/test architecture and existing Outline-related code.
- [x] Define one shared `OutlineSetupService` pipeline for API URL, SSH discovery, and Auto-Provision outputs; do not create separate server registration systems.
- [x] Add secure setup-session state with admin ownership, flow ID, method, optional existing server ID, creation/expiry, and no credential in callback data.
- [x] Implement API URL validation, HTTPS preference, supported-scheme/length/control-character checks, configurable SSRF/private-network policy, DNS/redirect safety, timeout, and redacted errors.
- [x] Implement Outline API URL connection, verification, safe metadata discovery, review/confirm/save flow, and atomic server integration.
- [x] Securely persist credential references/encrypted material without exposing API URLs in UI, logs, audit payloads, analytics, callbacks, or exception messages; clear temporary secret state on completion/cancel/expiry/failure.
- [x] Keep SSH and Auto-Provision visible but explicitly placeholder-only in Phase 3.2; never fake success or invoke remote installation.
- [x] Add bilingual Outline Setup UI, session prompts, verification states, and future-phase messages.
- [x] Add focused tests for URL/SSRF validation, credential redaction, session ownership/expiry, API verification failure/success, metadata confirmation, atomic persistence, idempotency/concurrency, no fake SSH/Auto-Provision success, and Phase 0–3.1 regressions.
- [x] Package one integrated master ZIP containing Phase 0 through Phase 3.2 and prepare the delivery report.

## Phase 3.3 — VPS / SSH Existing Outline Discovery

- [x] Inspect Phase 3.2 OutlineSetupService/client/credential vault, server/admin architecture, SSH dependencies, permissions, RequestContext, settings, events/audit, localization, migrations, and tests.
- [x] Define an admin-owned expiring SSH setup session with host, port, username, auth method, host-key state, and no raw password/private key in callbacks or long-lived Telegram state.
- [x] Implement SSH host validation, port/username validation, configurable timeouts, async-safe connection handling, and a safe host-key verification strategy.
- [x] Implement read-only SSH commands for OS/environment detection, existing Outline installation detection, and safe management API credential/certificate discovery.
- [x] Parse discovered Outline data without exposing credentials and hand `api_url + cert_sha256` into the existing Phase 3.2 `OutlineSetupService` pipeline.
- [x] Implement explicit `Outline Not Found` result and Phase 3.4 handoff marker; do not install packages, modify firewall, reboot, or auto-provision in Phase 3.3.
- [x] Integrate bilingual admin VPS/SSH authentication, progress, host-key confirmation, discovery result, retry/cancel, and API verification/review flow.
- [x] Add audit/event redaction, secure temporary credential cleanup, no-VPN-provisioning boundary, and focused SSH/discovery/security/regression tests.
- [ ] Package one integrated master ZIP containing Phase 0 through Phase 3.3 and prepare the delivery report.
