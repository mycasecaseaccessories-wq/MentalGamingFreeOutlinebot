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
- [x] Package one integrated master ZIP containing Phase 0 through Phase 3.3 and prepare the delivery report.

## Phase 3.4 — Fresh VPS Outline Auto-Provisioning

- [ ] Inspect Phase 3.3 SSH/discovery provider, setup sessions, command abstraction, Phase 3.2 OutlineSetupService, Phase 3.1 ServerService/Registry, admin handlers/keyboards, permissions, settings, audit/events, Result pattern, migrations, and tests.
- [ ] Define an idempotent provisioning state machine and server-side provisioning session with admin ownership, expiry, secret cleanup, and no credential in callbacks or logs.
- [ ] Implement read-only preflight for OS/version, architecture, privilege/root or controlled sudo, Docker, disk, memory, required commands, DNS/HTTPS connectivity, and narrow port-conflict checks.
- [ ] Reuse Phase 3.3 SSH infrastructure and existing Outline discovery before any mutation; route existing Outline to Phase 3.3/3.2 and never install a second copy automatically.
- [ ] Add supported-environment policy and typed provisioning plan/result with expected changes, risk flags, installer strategy, and explicit unsupported/insufficient-resource failures.
- [ ] Add a mandatory admin confirmation gate before any remote modification; confirmation must be one-time, ownership-safe, expiring, and idempotent.
- [ ] Implement a controlled, pinned, bounded Outline installer strategy with no raw admin input interpolation, no unbounded output/logging, and cleanup/failure recovery behavior.
- [ ] Parse installer output into sanitized `api_url + cert_sha256` credential data and hand it into the existing Phase 3.2 OutlineSetupService; do not duplicate verification or registration.
- [ ] Integrate bilingual Auto-Provision UI with preflight progress, confirmation summary, install progress, retry/cancel, existing Outline branch, failure states, and review/save flow.
- [ ] Ensure Phase 3.4 never generates customer VPN keys, allocates customer keys, creates customer access, or silently enables provisioning before Phase 3.2 verification/admin save.
- [ ] Add audit/events, redaction, settings, and focused tests for preflight, authorization, confirmation, existing-install safety, idempotency, parser security, command safety, failure recovery, no-customer-provisioning, and Phase 0–3.3 regressions.
- [ ] Package one integrated master ZIP containing Phase 0 through Phase 3.4 and prepare the delivery report.

## Phase 3.5 — Server Monitoring, Health & Synchronization

- [ ] Recover and review the Phase 3.5 specification attachment; request re-upload if unavailable.
- [ ] Inspect existing ServerService, HealthService, Outline API client/metrics, schema, migrations, scheduler, admin UI, localization, and Phase 3.1–3.4 boundaries.
- [ ] Define health states, metric freshness, sync contract, retry policy, stale-data behavior, and Phase 3.6 selection-safe read model.
- [ ] Implement server health and metrics synchronization using existing Outline and ServerService boundaries.
- [ ] Add durable periodic execution with idempotency and bounded concurrency; do not use in-process timers.
- [ ] Integrate bilingual admin server-list/detail health, key count, traffic, online/offline, and last-sync visibility.
- [ ] Add focused monitoring, stale-state, concurrency, metrics, failure-recovery, and Phase 3.1–3.4 regression tests.
- [ ] Package the integrated Phase 3.5 master ZIP and delivery report.
- [ ] Deliver Phase 3.5 archive, verification results, architecture choice, and Phase 3.6 handoff contract.

## Phase 3.6 — Automatic Server Selection

- [x] Recover and review the Phase 3.6 specification attachment; request re-upload if unavailable.
- [x] Inspect Phase 3.5 monitoring snapshot, server schema/repository, plan/country capabilities, payment/order boundaries, and Phase 4 key-creation contract.
- [x] Define eligibility filters, deterministic scoring, tie-breaking, no-server reasons, concurrency consistency, and SelectedServer DTO.
- [x] Implement pure selection engine for disabled, maintenance, offline, capacity, traffic, country, and plan filters.
- [x] Integrate selection service with existing server/monitoring read models without creating VPN keys or mutating customer state.
- [x] Add safe request/admin preview boundary, bilingual no-server explanations, and Phase 4 handoff metadata.
- [x] Add focused selection filters, scoring, tie-break, concurrency, no-key-creation, and Phase 3.1–3.5 regression tests.
- [x] Package Phase 3.6 master ZIP and delivery report.
- [x] Deliver Phase 3.6 archive, verification results, selection policy, and Phase 4 handoff contract.

- [x] Fix duplicate Phase 3.5 operational columns currently repeated in ServerORM before Phase 3.6 integration.

## Phase 3.6 Specification Completion Addendum

- [x] Reconcile the current selection implementation with the full Phase 3.6 attachment requirements.
- [x] Extend ServerSelectionRequest with workload, package, provider, required/preferred country, required/preferred server, capabilities, exclusions, fallback, reservation, and request reference fields.
- [x] Add centralized ServerEligibilityPolicy with configurable degraded/unknown/stale/unknown-capacity/unknown-traffic behavior and capacity/traffic headroom.
- [x] Add explicit preferred-country, required-country, preferred-server, required-server, provider, and exclusion fallback semantics.
- [x] Add configurable scoring strategy abstraction with score explanation, freshness/capacity/traffic/country components, and injectable deterministic randomness where used.
- [x] Add typed selection outcomes for country/provider/capability/capacity/traffic/health/stale failures and fallback-used metadata.
- [x] Add atomic ServerCapacityReservation model, migration, repository, and idempotent pending/commit/release/expire lifecycle.
- [x] Add reservation cleanup through the existing scheduler/task infrastructure and ensure reservations count against effective capacity.
- [x] Add structured selection/reservation events, safe operational logs/audit, settings validation, permissions, bilingual Load Balance screen, and dry-run simulator.
- [x] Add full specification-level tests for eligibility, headroom, unknown data, scoring, fallback, reservation concurrency, no-side-effect, no-live-provider-call, security, admin, and regression boundaries.
- [x] Repackage revised Phase 3.6 master ZIP and comprehensive delivery report.

## Phase 4.1 — VPN Provisioning Core & Outline Key Creation

- [ ] Inspect the complete Phase 4.1 attachment and existing VPNKey, CustomerKeyService, provider, order, package, selection, reservation, registry, event, hook, audit, settings, and test boundaries.
- [ ] Record the provider-neutral provisioning request/result contract and explicit provisioning state machine.
- [ ] Define authorization, idempotency identity, secret redaction, remote compensation, and local persistence transaction boundaries.
- [ ] Implement provisioning operation persistence and safe VPNKey binding migration/repository operations.
- [ ] Implement VPNProvisioningService using Phase 3.6 selection and Phase 3.6 capacity reservations.
- [ ] Revalidate the selected server before real Outline mutation and resolve provider through the existing registry.
- [ ] Create the remote Outline key, bind provider key metadata to one local VPNKey, and commit/release reservation safely.
- [ ] Add only authorized provisioning entry points; do not implement Phase 4.2–4.6 features.
- [ ] Add idempotency, authorization, reservation, provider mutation, compensation, redaction, binding, concurrency, and regression tests.
- [ ] Package the Phase 4.1 master ZIP and delivery report.
- [ ] Deliver Phase 4.1 archive, verification evidence, and Phase 4.2 handoff boundaries.

## Phase 4.3 — Duration / Expiration / VPN Key Lifecycle

- [x] Inspect lifecycle models, provider contract, task/scheduler foundation, order/package duration source, My Keys handlers, events, migrations, and tests.
- [x] Define trusted duration resolution, UTC activated_at/expires_at semantics, grace/expiring-soon policy, lifecycle transitions, and idempotent expiry contract.
- [x] Add lifecycle persistence migration 0019 with activation and provider-cleanup fields while preserving local key history.
- [x] Implement provider-neutral terminal revoke semantics, capability-aware suspension boundary, and retry-safe expiry cleanup task.
- [x] Register the expiry sweep through the existing scheduler with bounded batch, minimum interval, coalescing, and max_instances=1.
- [x] Integrate lifecycle service into registry/startup and add bilingual remaining-time/status display to My Keys.
- [x] Add focused Phase 4.3 policy/state tests; 4.2 + 4.3 focused suite passes 8 tests.
- [ ] Complete the full historical suite after reconciling active workspace migration visibility and inherited Phase 3.6 compatibility issues.
- [ ] Prepare and attach the final integrated Phase 4.3 archive and delivery report.
- [ ] Define Phase 4.4 handoff; renewal, automatic charging, full device limits, and free-trial claim rules remain excluded.

## Phase 4.4 — Secure Connect, Key Delivery & Device Policy

- [ ] Inspect Phase 4.1–4.3 VPNKey/provider/lifecycle/data-limit services, customer-key handlers/keyboards, authorization, storage/secret redaction, localization, settings, audit/events, and tests.
- [ ] Define ACTIVE-only Connect gate, secure access-key delivery/reveal policy, one-time/reveal audit boundary, and Outline app onboarding contract.
- [ ] Define device-limit policy source, counting/identity model, enforcement boundary, unknown-device behavior, and provider limitations without weakening key/data/time controls.
- [ ] Implement Connect page and secure key delivery with no secrets in callbacks, logs, lists, analytics, or unsafe history.
- [ ] Implement bilingual Outline app installation/import instructions and lifecycle-aware access denial states.
- [ ] Implement device-limit policy enforcement and authorized admin/customer controls without adding renewal or automatic charging.
- [ ] Add focused security tests for ownership/IDOR, ACTIVE-only access, secret redaction, replay/reveal behavior, device counting/limit, lifecycle/data-limit interaction, and bilingual UI.
- [ ] Run Phase 0–4.3 regression tests, prepare the Phase 4.4 delivery report, package the integrated master archive, and define the Phase 4.5 handoff.

## Phase 4.6 — Renewal, Key Rotation & Recovery

- [ ] Inspect Phase 4.1–4.5 renewal placeholders, VPNKey/order/payment/lifecycle/data-limit/access contracts, provider API, provisioning operations, scheduler/tasks, audit/events, notifications, registry, and tests.
- [ ] Define renewal eligibility, payment/terminal boundary, new-duration source, and idempotency identity without double charging or reactivating revoked keys.
- [ ] Define compromised/lost key replacement state machine and safe rotation order: create/bind/configure replacement first, then revoke old key.
- [ ] Define local-vs-Outline reconciliation states for missing remote keys, orphan remote keys, mismatched limits/lifecycle, and ambiguous provider outcomes.
- [ ] Implement failed/timeout provisioning recovery with bounded retries, operation locks, compensation, and duplicate-key prevention.
- [ ] Integrate bilingual customer/admin renewal, rotation, reconciliation, recovery status, audit, and notification controls.
- [ ] Add focused tests for ownership, payment boundary, renewal idempotency, rotation safety, provider timeout, local/remote drift, orphan handling, concurrency, and no-duplicate-key guarantees.
- [ ] Run Phase 0–4.5 regression tests, prepare the Phase 4.6 delivery report, package the integrated master archive, and define the Phase 4.7 handoff.
