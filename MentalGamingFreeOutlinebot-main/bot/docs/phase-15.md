# Phase 1.5 — My Keys UI & Customer VPN Key Status

Phase 1.5 adds an owner-scoped, read-only customer VPN key interface.

## Flow

Customer Main Menu → My Keys → Key Details → Usage / Connect / Renew Placeholder.

Both paid and free/history keys are listed together. A customer with zero
keys gets a normal empty state with Buy VPN, Free Trial, and Main Menu actions.

## Security

Every key lookup resolves the current Telegram user to the internal user ID and
uses `VPNKeyRepository.get_owned(key_id, user_id)`. Forged callbacks therefore
cannot reveal another customer's key. Full `access_url` values are never stored
in callback data and are never logged.

## Boundaries

This phase does not call Outline API, generate keys, revoke keys, renew keys,
mutate wallet balances, or process payments. Usage values are read only from the
local database and will be populated by the VPN Engine in Phase 4.

## Schema

Migration 0007 adds read-model fields: used_bytes, device_limit, package_id,
key_type, status, and last_synced_at while preserving the legacy is_active field.
