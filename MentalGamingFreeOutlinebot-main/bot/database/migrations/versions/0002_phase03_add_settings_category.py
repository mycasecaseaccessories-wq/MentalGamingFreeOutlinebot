"""Phase 0.3 — add category column to settings table.

Adds a nullable, indexed `category` column to the existing `settings` table
so that settings can be grouped by domain (general, vpn, wallet, etc.) in
the admin panel.

Uses batch mode for full SQLite compatibility (required when adding an
indexed column via ALTER TABLE on SQLite).

Revision ID: 0002
Revises:     0001
Create Date: 2025-08-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch operations for SQLite compatibility.
    # render_as_batch=True in env.py activates this for all dialects.
    with op.batch_alter_table("settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "category",
                sa.String(64),
                nullable=True,
                comment="Admin panel category slug — see SettingCategory in config.defaults",
            )
        )

    # Add index on category for get_category() performance.
    # Created after the column to keep the batch operation clean.
    op.create_index("ix_settings_category", "settings", ["category"])

    # Backfill existing rows: set category = 'general' so no NULL values
    # remain in the database after migration.
    op.execute(
        sa.text("UPDATE settings SET category = 'general' WHERE category IS NULL")
    )


def downgrade() -> None:
    op.drop_index("ix_settings_category", table_name="settings")
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("category")
