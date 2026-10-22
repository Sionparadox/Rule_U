"""Preserve evidence provenance at answer time."""
import sqlalchemy as sa
from alembic import op

revision = "20261022_citation_snapshot"
down_revision = "e70c67af5f40"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("citations", sa.Column("evidence_snapshot", sa.JSON(), nullable=False,
                                       server_default="{}"))


def downgrade():
    op.drop_column("citations", "evidence_snapshot")
