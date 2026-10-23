"""Answer diagnostics, BGG skip, feedback and saved rules."""
import sqlalchemy as sa
from alembic import op

revision = "20261023_feedback_saved_rules"
down_revision = "20261022_citation_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN: a batch rebuild would drop the unnamed status CHECK constraint.
    op.add_column("requests", sa.Column("diagnostic", sa.JSON(), nullable=True))
    op.add_column("requests", sa.Column("skip_external", sa.Boolean(), nullable=False,
                                        server_default=sa.false()))
    op.create_table(
        "answer_feedback",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("message_id", sa.String(), sa.ForeignKey("messages.id"), nullable=False,
                  unique=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("rating", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating IN ('helpful','wrong')"),
        sa.CheckConstraint(
            "reason IS NULL OR reason IN ('rule_differs','wrong_page','missing_info','other')"),
    )
    op.create_index("ix_answer_feedback_session_id", "answer_feedback", ["session_id"])
    op.create_table(
        "saved_rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("game_id", sa.String(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "message_id"),
    )
    op.create_index("ix_saved_rules_session_id", "saved_rules", ["session_id"])


def downgrade():
    op.drop_index("ix_saved_rules_session_id", "saved_rules")
    op.drop_table("saved_rules")
    op.drop_index("ix_answer_feedback_session_id", "answer_feedback")
    op.drop_table("answer_feedback")
    op.drop_column("requests", "skip_external")
    op.drop_column("requests", "diagnostic")
