"""Phase 0.4 — Role System, Authentication & Multi-Language Framework.

Adds authentication-related columns to users and roles tables:

  users:
    first_name   VARCHAR(128) nullable — first name from Telegram
    last_name    VARCHAR(128) nullable — last name from Telegram
    status       VARCHAR(16)  NOT NULL default 'active' — UserStatus
    last_active  DATETIME     nullable — last bot interaction timestamp

  roles:
    permissions  TEXT nullable — JSON array of Permission values

All changes use batch_alter_table for SQLite compatibility.

Revision ID: 0003
Revises:     0002
Create Date: 2025-08-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users table ──────────────────────────────────────────────────────────
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "first_name",
                sa.String(128),
                nullable=True,
                comment="First name from Telegram (Phase 0.4+)",
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_name",
                sa.String(128),
                nullable=True,
                comment="Last name from Telegram (optional)",
            )
        )
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(16),
                nullable=False,
                server_default="active",
                comment="UserStatus: active | inactive | suspended | banned | pending",
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_active",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="UTC timestamp of the user's last interaction with the bot",
            )
        )

    # Add index on status for fast status-based queries.
    op.create_index("ix_users_status", "users", ["status"])

    # ── roles table ───────────────────────────────────────────────────────────
    with op.batch_alter_table("roles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "permissions",
                sa.Text(),
                nullable=True,
                comment="JSON array of Permission values (e.g. '[\"manage_users\"]')",
            )
        )


def downgrade() -> None:
    op.drop_index("ix_users_status", table_name="users")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_active")
        batch_op.drop_column("status")
        batch_op.drop_column("last_name")
        batch_op.drop_column("first_name")

    with op.batch_alter_table("roles") as batch_op:
        batch_op.drop_column("permissions")
