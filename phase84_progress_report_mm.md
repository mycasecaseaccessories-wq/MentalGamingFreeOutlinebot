# Phase 8.4 — VPN / Outline Security Hardening Progress

## Architecture correction

The attached task description identifies a Node.js/CommonJS Telegram bot using MongoDB. The actual selected repository is a Python 3.12 Telegram bot using SQLAlchemy asyncio, Alembic, SQLite for local tests, and PostgreSQL as the production target. Phase 8.4 changes therefore target the actual Python repository; no Node.js/MongoDB architecture was introduced.

## Implemented in this iteration

The Outline management API verification path now requires and verifies a configured SHA-256 certificate fingerprint before making the API request. The implementation accepts the existing hexadecimal and `SHA256:`/base64 representations, rejects missing or malformed fingerprints, performs the live certificate check off the async event loop, and preserves `httpx` standard TLS verification, redirect rejection, safe error messages, and URL policy validation. The same authoritative server pin is now propagated into concrete Outline key creation and compensation deletion operations; alternate test/provider implementations retain their existing interface behavior.

The new executable tests cover valid hexadecimal fingerprints, prefixed fingerprints, base64 fingerprints, missing values, malformed values, and compatibility with existing Outline setup, server-sync, provisioning, and callback-security tests.

## Verification

| Check | Result |
|---|---:|
| Phase 8.4 TLS and related focused tests | **22 passed** in the latest focused run; 25 passed in the broader initial run |
| Full regression suite | Executed after the implementation; existing suite remains green in the available run |
| Compile | **PASS** |
| Outline TLS/client Ruff | **PASS** |
| Outline TLS/client Mypy | **PASS** |
| Phase 8.3 financial audit | **UNSAFE FINANCIAL MATCHES = 0** |

## Remaining Phase 8.4 work

Phase 8.4 is **in progress**, not complete. The remaining implementation areas are to audit VPN key ownership and IDOR boundaries, verify lifecycle and renewal replay behavior, review admin server operations for execution-time authorization and confirmation, validate provider response handling, and add the corresponding tests.

Phase 8.3 remains `NOT_SECURE / BLOCKED_PENDING_POSTGRESQL_VERIFICATION`; no PostgreSQL result was fabricated, and Phase 8.4 does not change that verdict.
