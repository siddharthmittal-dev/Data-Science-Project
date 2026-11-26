"""Password accounts: one registered account per role; retain existing records."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_hash", sa.String(256), nullable=True))
    op.create_index("uq_registered_role", "users", ["role"], unique=True,
                    postgresql_where=sa.text("password_hash IS NOT NULL"))
    # Sessions issued by the former role picker must authenticate again.
    op.execute("DELETE FROM sessions")


def downgrade():
    op.drop_index("uq_registered_role", table_name="users")
    op.drop_column("users", "password_hash")
