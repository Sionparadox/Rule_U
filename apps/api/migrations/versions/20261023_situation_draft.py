"""Conversation situation memo and streamed answer drafts."""
import sqlalchemy as sa
from alembic import op

revision = "20261023_situation_draft"
down_revision = "20261023_feedback_saved_rules"
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN keeps the existing unnamed CHECK constraints (no batch rebuild).
    op.add_column("conversations", sa.Column("situation", sa.JSON(), nullable=True))
    op.add_column("requests", sa.Column("draft", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("requests", "draft")
    op.drop_column("conversations", "situation")
