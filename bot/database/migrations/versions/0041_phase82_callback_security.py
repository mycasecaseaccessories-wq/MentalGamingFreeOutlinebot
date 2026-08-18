"""Phase 8.2 durable Telegram callback action security.

Revision ID: 0041_phase82_callback_security
Revises: 0040_phase81_admin_security
"""

import sqlalchemy as sa
from alembic import op

revision = "0041_phase82_callback_security"
down_revision = "0040_phase81_admin_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "callback_rate_limits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope_key", sa.String(length=192), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_key", name="uq_callback_rate_limit_scope"),
    )
    op.create_index(
        "ix_callback_rate_limits_scope_key", "callback_rate_limits", ["scope_key"], unique=True
    )

    op.create_table(
        "callback_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.String(length=48), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=96), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("chat_type", sa.String(length=32), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_public_id", sa.String(length=128), nullable=True),
        sa.Column("state_version", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.String(length=128), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("safe_metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_callback_action_public_id"),
        sa.UniqueConstraint("token_digest", name="uq_callback_action_token_digest"),
    )
    op.create_index("ix_callback_actions_public_id", "callback_actions", ["public_id"], unique=True)
    op.create_index(
        "ix_callback_actions_token_digest", "callback_actions", ["token_digest"], unique=True
    )
    op.create_index(
        "ix_callback_actions_action_type", "callback_actions", ["action_type"], unique=False
    )
    op.create_index(
        "ix_callback_actions_actor_user_id", "callback_actions", ["actor_user_id"], unique=False
    )
    op.create_index(
        "ix_callback_actions_actor_telegram_id",
        "callback_actions",
        ["actor_telegram_id"],
        unique=False,
    )
    op.create_index("ix_callback_actions_chat_id", "callback_actions", ["chat_id"], unique=False)
    op.create_index(
        "ix_callback_actions_resource_public_id",
        "callback_actions",
        ["resource_public_id"],
        unique=False,
    )
    op.create_index(
        "ix_callback_actions_expires_at", "callback_actions", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_callback_actions_expires_at", table_name="callback_actions")
    op.drop_index("ix_callback_actions_resource_public_id", table_name="callback_actions")
    op.drop_index("ix_callback_actions_chat_id", table_name="callback_actions")
    op.drop_index("ix_callback_actions_actor_telegram_id", table_name="callback_actions")
    op.drop_index("ix_callback_actions_actor_user_id", table_name="callback_actions")
    op.drop_index("ix_callback_actions_action_type", table_name="callback_actions")
    op.drop_index("ix_callback_actions_token_digest", table_name="callback_actions")
    op.drop_index("ix_callback_actions_public_id", table_name="callback_actions")
    op.drop_table("callback_actions")
    op.drop_index("ix_callback_rate_limits_scope_key", table_name="callback_rate_limits")
    op.drop_table("callback_rate_limits")
