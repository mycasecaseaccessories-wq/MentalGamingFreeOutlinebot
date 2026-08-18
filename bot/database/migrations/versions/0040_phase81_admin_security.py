"""phase 8.1 centralized admin security

Revision ID: 0040_phase81_admin_security
Revises: 0039_phase72_alert_notification_cycles
"""

import sqlalchemy as sa
from alembic import op

revision = "0040_phase81_admin_security"
down_revision = "0039_phase72_alert_notification_cycles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_principals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="admin"),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.BigInteger(), nullable=True),
        sa.Column("last_privileged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bootstrap_source", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("user_id", name="uq_admin_principal_user"),
    )
    op.create_index("ix_admin_principals_user_id", "admin_principals", ["user_id"], unique=True)
    op.create_index("ix_admin_principals_status", "admin_principals", ["status"], unique=False)
    op.create_index("ix_admin_principals_role", "admin_principals", ["role"], unique=False)
    op.create_index("ix_admin_principals_public_id", "admin_principals", ["public_id"], unique=True)

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index("ix_admin_sessions_public_id", "admin_sessions", ["public_id"], unique=True)
    op.create_index("ix_admin_sessions_principal_id", "admin_sessions", ["principal_id"], unique=False)
    op.create_index("ix_admin_sessions_token_digest", "admin_sessions", ["token_digest"], unique=True)
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"], unique=False)

    op.create_table(
        "admin_permission_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=64), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "principal_id", "permission", name="uq_admin_permission_principal_key"
        ),
    )
    op.create_index(
        "ix_admin_permission_grants_principal_id",
        "admin_permission_grants",
        ["principal_id"],
        unique=False,
    )
    op.create_index(
        "ix_admin_permission_grants_permission",
        "admin_permission_grants",
        ["permission"],
        unique=False,
    )

    op.create_table(
        "privileged_action_challenges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_safe_id", sa.String(length=128), nullable=True),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index(
        "ix_privileged_action_challenges_principal_id",
        "privileged_action_challenges",
        ["principal_id"],
        unique=False,
    )
    op.create_index(
        "ix_privileged_action_challenges_actor_telegram_id",
        "privileged_action_challenges",
        ["actor_telegram_id"],
        unique=False,
    )
    op.create_index(
        "ix_privileged_action_challenges_action_type",
        "privileged_action_challenges",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        "ix_privileged_action_challenges_expires_at",
        "privileged_action_challenges",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_privileged_action_challenges_public_id",
        "privileged_action_challenges",
        ["public_id"],
        unique=True,
    )

    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="warning"),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_principal_id", sa.Integer(), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_safe_id", sa.String(length=128), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("safe_error_code", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("event_type", "event_type"),
        ("actor_user_id", "actor_user_id"),
        ("actor_principal_id", "actor_principal_id"),
    ):
        op.create_index(f"ix_security_events_{name}", "security_events", [column], unique=False)


def downgrade() -> None:
    for name in (
        "ix_security_events_actor_principal_id",
        "ix_security_events_actor_user_id",
        "ix_security_events_event_type",
    ):
        op.drop_index(name, table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("ix_privileged_action_challenges_public_id", table_name="privileged_action_challenges")
    op.drop_index("ix_privileged_action_challenges_expires_at", table_name="privileged_action_challenges")
    op.drop_index("ix_privileged_action_challenges_action_type", table_name="privileged_action_challenges")
    op.drop_index("ix_privileged_action_challenges_actor_telegram_id", table_name="privileged_action_challenges")
    op.drop_index("ix_privileged_action_challenges_principal_id", table_name="privileged_action_challenges")
    op.drop_table("privileged_action_challenges")
    op.drop_index("ix_admin_permission_grants_permission", table_name="admin_permission_grants")
    op.drop_index("ix_admin_permission_grants_principal_id", table_name="admin_permission_grants")
    op.drop_table("admin_permission_grants")
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_token_digest", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_principal_id", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_public_id", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_index("ix_admin_principals_public_id", table_name="admin_principals")
    op.drop_index("ix_admin_principals_role", table_name="admin_principals")
    op.drop_index("ix_admin_principals_status", table_name="admin_principals")
    op.drop_index("ix_admin_principals_user_id", table_name="admin_principals")
    op.drop_table("admin_principals")
