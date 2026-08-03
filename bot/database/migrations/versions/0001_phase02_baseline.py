"""Phase 0.2 baseline — initial schema for all platform tables.

Creates all 13 tables established in Phase 0.2.
This is the starting point for Alembic version tracking.
Databases that were already created with create_all() should be
stamped at this revision via: alembic stamp 0001

Revision ID: 0001
Revises:     (none)
Create Date: 2025-08-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, comment="Unique Telegram user ID"),
        sa.Column("username", sa.String(64), nullable=True, comment="Telegram @username (without @)"),
        sa.Column("full_name", sa.String(255), nullable=False, comment="Display name from Telegram"),
        sa.Column("role", sa.String(32), nullable=False, comment="User role: customer | admin | reseller | affiliate"),
        sa.Column("language", sa.String(8), nullable=False, comment="UI language code: en | my"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="False when the account is banned"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, comment="True after identity verification"),
        sa.Column("referred_by", sa.BigInteger(), nullable=True, comment="Telegram ID of the referrer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    # ── roles ─────────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("name", sa.String(32), nullable=False, comment="Role identifier: customer | admin | reseller | affiliate"),
        sa.Column("label", sa.String(64), nullable=False, comment="Human-readable role label"),
        sa.Column("description", sa.Text(), nullable=True, comment="What this role can do"),
        sa.Column("is_system", sa.Boolean(), nullable=False, comment="True for built-in roles that cannot be deleted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── packages ──────────────────────────────────────────────────────────────
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("name", sa.String(128), nullable=False, comment="Display name (e.g. '30-Day Basic')"),
        sa.Column("description", sa.Text(), nullable=True, comment="Marketing description shown to users"),
        sa.Column("price", sa.Numeric(12, 2), nullable=False, comment="Package price in the default currency"),
        sa.Column("currency", sa.String(3), nullable=False, comment="ISO 4217 currency code"),
        sa.Column("duration_days", sa.Integer(), nullable=False, comment="Subscription duration in days"),
        sa.Column("data_limit_gb", sa.Numeric(10, 2), nullable=True, comment="Data cap in gigabytes (NULL = unlimited)"),
        sa.Column("max_devices", sa.Integer(), nullable=True, comment="Max simultaneous VPN keys (NULL = platform default)"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="False hides the package from users"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="Display order in package listings"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── servers ───────────────────────────────────────────────────────────────
    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("name", sa.String(128), nullable=False, comment="Human-readable server label"),
        sa.Column("api_url", sa.String(512), nullable=False, comment="Outline Management API base URL"),
        sa.Column("cert_sha256", sa.String(64), nullable=False, comment="TLS certificate SHA-256 fingerprint"),
        sa.Column("region", sa.String(64), nullable=True, comment="Geographic region label (e.g. 'Southeast Asia')"),
        sa.Column("country_code", sa.String(2), nullable=True, comment="ISO 3166-1 alpha-2 country code"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="False takes the server out of rotation"),
        sa.Column("max_keys", sa.Integer(), nullable=True, comment="Key capacity limit (NULL = unlimited)"),
        sa.Column("notes", sa.Text(), nullable=True, comment="Internal admin notes"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_url"),
    )

    # ── vpn_keys ──────────────────────────────────────────────────────────────
    op.create_table(
        "vpn_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="FK → users.id"),
        sa.Column("server_id", sa.Integer(), nullable=False, comment="FK → servers.id"),
        sa.Column("outline_key_id", sa.Integer(), nullable=False, comment="Numeric key ID assigned by the Outline server"),
        sa.Column("access_url", sa.Text(), nullable=False, comment="ss:// URI users import into their Outline client"),
        sa.Column("name", sa.String(128), nullable=True, comment="Optional friendly label for this key"),
        sa.Column("data_limit_bytes", sa.BigInteger(), nullable=True, comment="Per-key data cap in bytes (NULL = no cap)"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="False = key is revoked"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="UTC expiry timestamp (NULL = never)"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vpn_keys_user_id", "vpn_keys", ["user_id"])
    op.create_index("ix_vpn_keys_server_id", "vpn_keys", ["server_id"])

    # ── wallets ───────────────────────────────────────────────────────────────
    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="FK → users.id — one wallet per user"),
        sa.Column("balance", sa.Numeric(14, 4), nullable=False, comment="Current balance — always derived from transaction ledger"),
        sa.Column("currency", sa.String(3), nullable=False, comment="ISO 4217 currency code for this wallet"),
        sa.Column("is_frozen", sa.Boolean(), nullable=False, comment="True when the wallet is locked (fraud hold / admin action)"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallets_user_id", "wallets", ["user_id"], unique=True)

    # ── orders ────────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="FK → users.id"),
        sa.Column("package_id", sa.Integer(), nullable=False, comment="FK → packages.id"),
        sa.Column("vpn_key_id", sa.Integer(), nullable=True, comment="FK → vpn_keys.id (set after provisioning)"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, comment="Amount charged for this order"),
        sa.Column("currency", sa.String(3), nullable=False, comment="ISO 4217 currency code"),
        sa.Column("status", sa.String(16), nullable=False, comment="Order lifecycle: pending | paid | active | expired | cancelled | refunded"),
        sa.Column("payment_ref", sa.String(256), nullable=True, comment="External payment gateway reference"),
        sa.Column("notes", sa.Text(), nullable=True, comment="Internal admin notes"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    # ── transactions ──────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("wallet_id", sa.Integer(), nullable=False, comment="FK → wallets.id"),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False, comment="Signed amount: positive = credit, negative = debit"),
        sa.Column("currency", sa.String(3), nullable=False, comment="ISO 4217 currency code"),
        sa.Column("type", sa.String(32), nullable=False, comment="Transaction type: topup | purchase | refund | commission | adjustment"),
        sa.Column("reference", sa.String(256), nullable=True, comment="Optional external reference (payment ID, order ID, etc.)"),
        sa.Column("note", sa.Text(), nullable=True, comment="Human-readable note for admin audit trail"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_wallet_id", "transactions", ["wallet_id"])
    op.create_index("ix_transactions_type", "transactions", ["type"])

    # ── referrals ─────────────────────────────────────────────────────────────
    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("referrer_id", sa.Integer(), nullable=False, comment="FK → users.id of the referrer"),
        sa.Column("referred_id", sa.Integer(), nullable=False, comment="FK → users.id of the new user (unique — one referral per user)"),
        sa.Column("status", sa.String(16), nullable=False, comment="Referral lifecycle: pending | qualified | paid | rejected"),
        sa.Column("commission", sa.Numeric(12, 4), nullable=True, comment="Commission amount earned (set when qualified)"),
        sa.Column("currency", sa.String(3), nullable=True, comment="ISO 4217 code for the commission amount"),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True, comment="UTC timestamp when the referral became eligible for commission"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_id"),
    )
    op.create_index("ix_referrals_referrer_id", "referrals", ["referrer_id"])
    op.create_index("ix_referrals_status", "referrals", ["status"])

    # ── free_trials ───────────────────────────────────────────────────────────
    op.create_table(
        "free_trials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="FK → users.id — one trial per user"),
        sa.Column("vpn_key_id", sa.Integer(), nullable=True, comment="FK → vpn_keys.id — set when the trial key is issued"),
        sa.Column("duration_days", sa.Integer(), nullable=False, comment="Trial duration in days"),
        sa.Column("is_used", sa.Boolean(), nullable=False, comment="True once the trial has been activated"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="UTC timestamp when the trial key auto-revokes"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_free_trials_user_id", "free_trials", ["user_id"])

    # ── settings ──────────────────────────────────────────────────────────────
    # Phase 0.2 schema — WITHOUT category column (added in migration 0002).
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("key", sa.String(128), nullable=False, comment="Unique setting key — use snake_case (e.g. force_join_enabled)"),
        sa.Column("value", sa.Text(), nullable=False, comment="Setting value stored as string — cast using the type column"),
        sa.Column("type", sa.String(16), nullable=False, comment="Value type hint: str | int | float | bool | json | list"),
        sa.Column("description", sa.Text(), nullable=True, comment="Human-readable description shown in the admin settings panel"),
        sa.Column("is_public", sa.Boolean(), nullable=False, comment="True if non-admin code can read this setting"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_settings_key", "settings", ["key"], unique=True)

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="FK → users.id"),
        sa.Column("type", sa.String(64), nullable=False, comment="Notification type: expiry_reminder | broadcast | payment_receipt | system_alert"),
        sa.Column("channel", sa.String(16), nullable=False, comment="Delivery channel: telegram | sms | email"),
        sa.Column("subject", sa.String(256), nullable=True, comment="Optional subject line (used for email channel)"),
        sa.Column("body", sa.Text(), nullable=False, comment="Message body — plain text or Telegram HTML"),
        sa.Column("status", sa.String(16), nullable=False, comment="Delivery lifecycle: queued | sent | failed | cancelled"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True, comment="UTC timestamp when the message was delivered"),
        sa.Column("error", sa.Text(), nullable=True, comment="Error message from the last failed delivery attempt"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Auto-incrementing primary key"),
        sa.Column("actor_id", sa.Integer(), nullable=True, comment="FK → users.id (NULL for system-generated events)"),
        sa.Column("action", sa.String(128), nullable=False, comment="Action identifier (e.g. user.ban, key.revoke, setting.update)"),
        sa.Column("entity_type", sa.String(64), nullable=True, comment="Target entity type (e.g. 'user', 'vpn_key', 'order')"),
        sa.Column("entity_id", sa.Integer(), nullable=True, comment="Target entity primary key"),
        sa.Column("old_value", sa.Text(), nullable=True, comment="JSON-serialised state before the action"),
        sa.Column("new_value", sa.Text(), nullable=True, comment="JSON-serialised state after the action"),
        sa.Column("ip_address", sa.String(45), nullable=True, comment="IPv4 or IPv6 address of the actor"),
        sa.Column("note", sa.Text(), nullable=True, comment="Free-text admin note"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of record creation"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="UTC timestamp of last record update"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("settings")
    op.drop_table("free_trials")
    op.drop_table("referrals")
    op.drop_table("transactions")
    op.drop_table("orders")
    op.drop_table("wallets")
    op.drop_table("vpn_keys")
    op.drop_table("servers")
    op.drop_table("packages")
    op.drop_table("roles")
    op.drop_table("users")
