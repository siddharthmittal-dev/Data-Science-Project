"""Booking retries and internal follow-up tasks."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("booking_requests",
                    sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
                    sa.Column("key", sa.String(100), primary_key=True),
                    sa.Column("signature", sa.String(64), nullable=False),
                    sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False))
    op.create_table("follow_up_tasks",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("note", sa.String(500), nullable=False),
                    sa.Column("outcome", sa.String(500), nullable=False, server_default=""),
                    sa.Column("status", sa.String(20), nullable=False, server_default="open"),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                    sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index("uq_follow_up_open_patient", "follow_up_tasks", ["patient_id"], unique=True,
                    postgresql_where=sa.text("status = 'open'"))


def downgrade():
    op.drop_table("follow_up_tasks")
    op.drop_table("booking_requests")
