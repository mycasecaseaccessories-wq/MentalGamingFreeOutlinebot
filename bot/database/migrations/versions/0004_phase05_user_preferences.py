"""Phase 0.5 — User Preferences architecture.

Creates the user_preferences table with one row per user.
All preference fields have sensible defaults so existing users who
never explicitly set a preference get correct fallback behaviour.

Schema:
    user_preferences
      id                       INTEGER  PK AUTOINCREMENT
      user_id                  BIGINT   UNIQUE NOT NULL  (app-level FK → users.telegram_id)
      language                 VARCHAR(8)   NOT NULL  default 'en'
      timezone                 VARCHAR(64)  NOT NULL  default 'Asia/Rangoon'
      preferred_currency       VARCHAR(8)   NOT NULL  default 'MMK'
      notification_enabled     BOOLEAN      NOT NULL  default TRUE
      broadcast_enabled        BOOLEAN      NOT NULL  default TRUE
      privacy_mode             BOOLEAN      NOT NULL  default FALSE
      theme                    VARCHAR(32)  NOT NULL  default 'default'
      last_menu                VARCHAR(64)  nullable
      preferred_server_country VARCHAR(64)  nullable
      created_at               DATETIME     NOT NULL
      updated_at               DATETIME     NOT NULL

Revision ID: 0004
Revises:     0003
Create Date: 2025-08-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("id",         sa.Integer(),    nullable=False, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
            comment="Telegram user ID — mirrors users.telegram_id (app-level FK)",
        ),
        # Language & region
        sa.Column(
            "language", sa.String(8), nullable=False, server_default="en",
            comment="Preferred UI language code",
        ),
        sa.Column(
            "timezone", sa.String(64), nullable=False, server_default="Asia/Rangoon",
            comment="IANA timezone string",
        ),
        sa.Column(
            "preferred_currency", sa.String(8), nullable=False, server_default="MMK",
            comment="ISO 4217 currency code",
        ),
        # Notifications
        sa.Column(
            "notification_enabled", sa.Boolean(), nullable=False, server_default=sa.true(),
            comment="Receive expiry/renewal/system notifications",
        ),
        sa.Column(
            "broadcast_enabled", sa.Boolean(), nullable=False, server_default=sa.true(),
            comment="Receive admin broadcast messages",
        ),
        # Privacy
        sa.Column(
            "privacy_mode", sa.Boolean(), nullable=False, server_default=sa.false(),
            comment="Minimise data logging and sensitive field display",
        ),
        # UI / theme
        sa.Column(
            "theme", sa.String(32), nullable=False, server_default="default",
            comment="Mini App UI theme token",
        ),
        sa.Column(
            "last_menu", sa.String(64), nullable=True,
            comment="Last visited menu identifier for navigation state restore",
        ),
        # Server preference
        sa.Column(
            "preferred_server_country", sa.String(64), nullable=True,
            comment="ISO 3166-1 alpha-2 preferred VPN server country",
        ),
        # Audit timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
