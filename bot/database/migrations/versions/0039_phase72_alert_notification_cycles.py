"""phase72 alert notification cycles

Revision ID: 0039_phase72_alert_notification_cycles
Revises: 0038_phase72_operational_alerts
"""

import sqlalchemy as sa
from alembic import op

revision = "0039_phase72_alert_notification_cycles"
down_revision = "0038_phase72_operational_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "operational_alerts",
        sa.Column(
            "notification_state", sa.String(length=24), nullable=False, server_default="none"
        ),
    )
    op.add_column(
        "operational_alerts",
        sa.Column("notification_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("operational_alerts", "notification_attempts")
    op.drop_column("operational_alerts", "notification_state")
