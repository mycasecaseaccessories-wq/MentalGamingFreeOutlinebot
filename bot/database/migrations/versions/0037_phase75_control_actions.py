"""Phase 7.5 completion hardening — durable control actions."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0037_phase75_control_actions"
down_revision = "0036_phase75_maintenance_incidents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("window_id", sa.Integer(), nullable=True),
        sa.Column("result_code", sa.String(48), nullable=False, server_default="accepted"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_maintenance_actions_idempotency_key"),
    )
    op.create_index("ix_maintenance_actions_actor_id", "maintenance_actions", ["actor_id"])
    op.create_index("ix_maintenance_actions_actor_created", "maintenance_actions", ["actor_id", "created_at"])
    op.create_index("ix_maintenance_actions_window_id", "maintenance_actions", ["window_id"])
    op.create_index("ix_maintenance_actions_window_action", "maintenance_actions", ["window_id", "action"])


def downgrade() -> None:
    op.drop_index("ix_maintenance_actions_window_action", table_name="maintenance_actions")
    op.drop_index("ix_maintenance_actions_window_id", table_name="maintenance_actions")
    op.drop_index("ix_maintenance_actions_actor_created", table_name="maintenance_actions")
    op.drop_index("ix_maintenance_actions_actor_id", table_name="maintenance_actions")
    op.drop_table("maintenance_actions")
