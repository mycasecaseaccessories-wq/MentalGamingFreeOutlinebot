# Phase 4.2 — GB / Data Limit Enforcement & Usage Binding

## Implemented scope

Phase 4.2 extends the Phase 4.1 VPN key binding with byte-based data-limit policy, exact provider-key limit application, provider read-back, usage baseline, effective usage, remaining bytes, last usage sync time, and a separate limit lifecycle state. The supported lifecycle is `not_configured`, `pending`, `applied`, `failed`, `unsupported`, and `drifted`.

For paid orders, the authoritative source is the immutable `OrderORM.data_limit_gb_snapshot`; Telegram or callback-provided GB values are not trusted. The project convention is binary gigabytes, where 1 GB is 1024³ bytes. A retry with a different limit than the paid-order snapshot returns a conflict instead of silently changing the plan.

The Outline provider now targets the exact bound provider key with `PUT /access-keys/{id}/data-limit`, reads the key back with `GET /access-keys/{id}`, and reads per-key usage using `/metrics/transfer`. The remote usage counter is converted into lifecycle usage by subtracting the stored baseline and clamping at zero. A later read-back mismatch is recorded as `drifted`; a remote-success/local-failure retry is designed to reapply the same authoritative limit rather than remove the cap.

The existing customer key service remains the presentation boundary. Its usage summary can refresh the exact key usage through the Phase 4.2 service, then returns used bytes, remaining bytes, percentage, last sync time, limit status, and provider verification state. No expiration automation, device-limit enforcement, or renewal flow has been added.

## Official API verification

The official Outline Server API specification documents `PUT /access-keys/{id}/data-limit` with a JSON body containing `{"limit": {"bytes": <integer>}}`, `GET /access-keys/{id}` with a `dataLimit` response object, and `GET /metrics/transfer` with `bytesTransferredByUserId`. Reference: [Outline Server API specification](https://raw.githubusercontent.com/Jigsaw-Code/outline-server/master/src/shadowbox/server/api.yml).

## Verification status

The Phase 4.2 source was syntax-checked during implementation. The focused test file was added for GB conversion, invalid-limit validation, remaining-byte clamping, and status separation. The current shell test runner intermittently cannot see newly created files from the canonical workspace, so the focused pytest run is recorded as blocked by the environment path visibility issue rather than reported as passing. The inherited Phase 3.6 regression mismatch remains a separate pending item.

## Phase 4.3 boundary

The next phase may add scheduled or event-driven usage synchronization, notifications when a cap is reached, and reconciliation workers. It must preserve this phase's authoritative order snapshot, exact-key provider identity, idempotent reapplication, baseline arithmetic, drift state, and explicit exclusion of expiry, device-limit, and renewal behavior until those features are separately approved.
