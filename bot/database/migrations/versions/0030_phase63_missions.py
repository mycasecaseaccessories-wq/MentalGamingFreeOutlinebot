"""Phase 6.3 missions and shared reward provenance."""
from alembic import op
import sqlalchemy as sa

revision = "0030_phase63_missions"
down_revision = "0029_phase62_referral_rewards"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("referral_rewards", schema=None) as batch:
        batch.add_column(sa.Column("source_type", sa.String(32), nullable=True, server_default="referral"))
        batch.add_column(sa.Column("source_reference", sa.String(160), nullable=True, server_default="referral"))
        batch.alter_column("referral_id", existing_type=sa.Integer(), nullable=True)
    op.execute("UPDATE referral_rewards SET source_type = 'referral' WHERE source_type IS NULL")
    op.execute("UPDATE referral_rewards SET source_reference = CAST(referral_id AS TEXT) WHERE source_reference IS NULL")
    with op.batch_alter_table("referral_rewards", schema=None) as batch:
        batch.alter_column("source_type", existing_type=sa.String(32), nullable=False, server_default=None)
        batch.alter_column("source_reference", existing_type=sa.String(160), nullable=False, server_default=None)
    op.create_index("ix_referral_rewards_source_type", "referral_rewards", ["source_type"])

    op.create_table(
        "missions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_mission_id", sa.String(48), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mission_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("condition_config", sa.JSON(), nullable=False),
        sa.Column("reward_type", sa.String(32), nullable=False),
        sa.Column("reward_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("reward_expiry_seconds", sa.Integer(), nullable=False),
        sa.Column("delivery_mode", sa.String(24), nullable=False),
        sa.Column("repeat_mode", sa.String(24), nullable=False),
        sa.Column("progress_target", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False),
        sa.Column("reset_timezone", sa.String(64), nullable=False),
        sa.Column("eligibility_mode", sa.String(32), nullable=False),
        sa.Column("eligibility_config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint("public_mission_id", name="uq_missions_public_id"),
        sa.UniqueConstraint("public_mission_id", "policy_revision", name="uq_mission_public_revision"),
    )
    for name, cols in (
        ("ix_missions_public_mission_id", ["public_mission_id"]),
        ("ix_missions_mission_type", ["mission_type"]),
        ("ix_missions_status", ["status"]),
        ("ix_missions_starts_at", ["starts_at"]),
        ("ix_missions_ends_at", ["ends_at"]),
        ("ix_missions_enabled", ["enabled"]),
    ):
        op.create_index(name, "missions", cols)

    op.create_table(
        "user_mission_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_progress_id", sa.String(48), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("period_key", sa.String(80), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_value", sa.Integer(), nullable=False),
        sa.Column("target_value_snapshot", sa.Integer(), nullable=False),
        sa.Column("mission_revision", sa.Integer(), nullable=False),
        sa.Column("reward_type_snapshot", sa.String(32), nullable=False),
        sa.Column("reward_value_snapshot", sa.Numeric(18, 4), nullable=False),
        sa.Column("reward_expiry_seconds_snapshot", sa.Integer(), nullable=False),
        sa.Column("delivery_mode_snapshot", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_id", sa.Integer(), nullable=True),
        sa.Column("reward_public_id", sa.String(48), nullable=True),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("last_source_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(256), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_mission_progress_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], name="fk_mission_progress_mission", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reward_id"], ["referral_rewards.id"], name="fk_mission_progress_reward", ondelete="RESTRICT"),
        sa.UniqueConstraint("public_progress_id", name="uq_mission_progress_public_id"),
        sa.UniqueConstraint("user_id", "mission_id", "period_key", name="uq_user_mission_progress_period"),
        sa.UniqueConstraint("idempotency_key", name="uq_user_mission_progress_idempotency"),
        sa.UniqueConstraint("reward_id", name="uq_mission_progress_reward_id"),
        sa.UniqueConstraint("reward_public_id", name="uq_mission_progress_reward_public_id"),
    )
    for name, cols in (
        ("ix_user_mission_progress_public_id", ["public_progress_id"]),
        ("ix_user_mission_progress_user_id", ["user_id"]),
        ("ix_user_mission_progress_mission_id", ["mission_id"]),
        ("ix_user_mission_progress_period_key", ["period_key"]),
        ("ix_user_mission_progress_status", ["status"]),
        ("ix_user_mission_progress_idempotency_key", ["idempotency_key"]),
    ):
        op.create_index(name, "user_mission_progress", cols)

    op.create_table(
        "mission_progress_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("progress_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_reference", sa.String(160), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("period_key", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], name="fk_mission_event_mission", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_mission_event_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["progress_id"], ["user_mission_progress.id"], name="fk_mission_event_progress", ondelete="RESTRICT"),
        sa.UniqueConstraint("idempotency_key", name="uq_mission_progress_event_idempotency"),
    )
    for name, cols in (
        ("ix_mission_progress_events_mission_id", ["mission_id"]),
        ("ix_mission_progress_events_user_id", ["user_id"]),
        ("ix_mission_progress_events_progress_id", ["progress_id"]),
        ("ix_mission_progress_events_source_type", ["source_type"]),
        ("ix_mission_progress_events_period_key", ["period_key"]),
        ("ix_mission_progress_events_idempotency_key", ["idempotency_key"]),
    ):
        op.create_index(name, "mission_progress_events", cols)


def downgrade():
    for name in ("ix_mission_progress_events_idempotency_key", "ix_mission_progress_events_period_key", "ix_mission_progress_events_source_type", "ix_mission_progress_events_progress_id", "ix_mission_progress_events_user_id", "ix_mission_progress_events_mission_id"):
        op.drop_index(name, table_name="mission_progress_events")
    op.drop_table("mission_progress_events")
    for name in ("ix_user_mission_progress_idempotency_key", "ix_user_mission_progress_status", "ix_user_mission_progress_period_key", "ix_user_mission_progress_mission_id", "ix_user_mission_progress_user_id", "ix_user_mission_progress_public_id"):
        op.drop_index(name, table_name="user_mission_progress")
    op.drop_table("user_mission_progress")
    for name in ("ix_missions_enabled", "ix_missions_ends_at", "ix_missions_starts_at", "ix_missions_status", "ix_missions_mission_type", "ix_missions_public_mission_id"):
        op.drop_index(name, table_name="missions")
    op.drop_table("missions")
    op.drop_index("ix_referral_rewards_source_type", table_name="referral_rewards")
    with op.batch_alter_table("referral_rewards", schema=None) as batch:
        batch.drop_column("source_reference")
        batch.drop_column("source_type")
        batch.alter_column("referral_id", existing_type=sa.Integer(), nullable=False)
