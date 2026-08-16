# Phase 3.4 Delivery Report

## Scope

Phase 3.4 adds secure Fresh-VPS Outline Auto-Provisioning. The implementation reuses the Phase 3.3 `SSHDiscoveryProvider` for host-key-gated SSH operations and routes installer credentials through the Phase 3.2 `OutlineSetupService` for Outline API verification, encrypted persistence, and the existing Phase 3.1 server-registration path.

## Implemented

| Area | Implementation | Safety boundary |
|---|---|---|
| Provisioning state | `OutlineProvisioningService` with expiring admin-owned sessions | Installation cannot start before a one-time confirmation token |
| Preflight | OS, architecture, privilege, Docker, disk, memory, required commands, DNS/HTTPS, and listening-port inspection | Preflight is read-only |
| Existing Outline | Discovery branch sends discovered credential to `OutlineSetupService` | No installer command is executed when Outline already exists |
| Installer | Centrally configured HTTPS official installer strategy with bounded timeout and output limits | No Telegram-supplied URL or shell command is accepted |
| Secret handling | URL/certificate values are parsed in memory and excluded from result repr/audit payloads | Raw installer stdout/stderr is not logged or shown |
| Verification | Installer result becomes `OutlineCredentialInput(source="auto_provision")` and uses Phase 3.2 verification | Exit code alone never marks success |
| Admin UI | SSH details, preflight plan, explicit confirmation, install progress, review, and save actions | Remote modification is clearly disclosed before confirmation |
| Localization | English and Myanmar provisioning strings | UI remains bilingual |
| Events | Provisioning started, preflight completed, install started/completed, verification failed, completed, and failed events | Payloads exclude credentials |
| Customer boundary | No call to customer key generation or VPN issuance exists in Phase 3.4 | Server setup only; customer VPN keys remain untouched |

## Verification

The focused Phase 3.4 suite passes: **3 passed**. Python compilation of the changed application and locale modules also passes.

The full historical suite ran with test-only `BOT_TOKEN` and `SESSION_SECRET` values. It reported **336 passed**, with **13 failed** and **6 collection errors**. The failures include migration-head expectations for revision `0008` versus the already-present `0013`, missing `database.db` in service-registry integration fixtures, and unrelated legacy plugin, pagination, security, versioning, and customer-navigation assertions. These are recorded as existing repository regression/environment issues rather than attributed to the Phase 3.4 changes.

## Operational boundaries

The implementation does not automatically uninstall Docker or Outline after a partial failure, does not issue a VPS reboot, does not expose arbitrary Docker/firewall/shell administration, and does not persist SSH credentials by default. If remote installation starts and later verification fails, the service preserves a retryable failure state and avoids claiming that remote changes were rolled back.

The generated archive is intended for code review and integration testing. A real deployment must supply the repository's normal production secrets, apply the migration chain in the target environment, validate the official installer source against the organization's release policy, and test with a disposable VPS before enabling production use.
