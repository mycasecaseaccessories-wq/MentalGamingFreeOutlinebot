# Phase 4.1 Delivery Report — VPN Provisioning Core

## Scope

Phase 4.1 adds provider-neutral VPN provisioning for servers selected by the Phase 3.6 engine. The implementation is deliberately manual-entry driven: payment approval does not automatically create a VPN key, and expiry, GB-limit automation, and automatic paid-order triggers are outside this phase.

## Implemented

The provisioning core now exposes `VPNProvisioningRequest`, `VPNProvisioningSuccess`, and lifecycle status/failure enums. Every request requires an explicit idempotency key and request reference. Provisioning is authorized for the owning customer or an active administrator.

The saga persists durable operation records in `vpn_provisioning_operations`. Its lifecycle is Select → Reserve → Create Remote → Persist Local → Commit, with explicit `unknown` and `compensation_required` states. A remote Outline key is deleted when local persistence fails; if deletion fails, the operation remains marked for administrator reconciliation. Sensitive management URLs are not included in result representations or event payloads.

`VPNKeyORM` now binds provider identity, order identity, provisioning operation identity, source type, and provisioned timestamp. The database migration chain contains revisions `0016` and `0017` for the operation table and VPN-key binding constraints/indexes.

`VPNProvisioningEntryService` provides two explicit bilingual entry points: customer provisioning for the owner of a paid order and administrator provisioning for a customer paid order. It does not subscribe to payment approval events, so the Phase 4.1 boundary remains intact.

## Verification

| Check | Result |
|---|---|
| Phase 4.1 model/provider/service scoped compilation | Passed |
| Registry and manual entry service compilation | Passed |
| Provider-safe naming and request-validation focused checks | Passed in inherited verification |
| Full pytest collection | Blocked by existing environment assumptions and a legacy Phase 3.6 test/API mismatch |
| Phase 3.6 legacy selection tests | Not green in the inherited tree; the test expects `ServerSelectionEngine`, while the active source copy has a differing selection implementation and test fixtures omit some production fields |

The test blocker is recorded rather than hidden. No automated provisioning trigger was added to bypass it.

## Phase 4.2 Handoff Contract

Phase 4.2 may add expiry and traffic-limit enforcement only through a separate automation design. It must consume the durable provisioning operation state, preserve idempotency, and define retry/reconciliation behavior for `unknown` and `compensation_required` operations. It must not infer that a screenshot, payment approval event, or stale local key record is sufficient proof that a remote key exists.
