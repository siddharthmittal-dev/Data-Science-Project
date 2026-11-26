"""Preserve appointment changes without inventing historical events."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("slot_id", sa.Integer(), sa.ForeignKey("slots.id"), nullable=False),
        sa.Column("previous_slot_id", sa.Integer(), sa.ForeignKey("slots.id")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointment_events_appointment_id", "appointment_events", ["appointment_id"])
    # Snapshot, not a fabricated booking timestamp. Earlier changes are unknown.
    op.execute("""INSERT INTO appointment_events
        (appointment_id, kind, slot_id, status, occurred_at)
        SELECT id, 'snapshot', slot_id, status, CURRENT_TIMESTAMP FROM appointments""")


def downgrade() -> None:
    op.drop_table("appointment_events")
