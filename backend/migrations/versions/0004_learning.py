"""Append-only grading revisions and workspace learning plans."""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("attempts", sa.Column("question_revision", sa.Integer(), nullable=True))
    op.add_column("attempts", sa.Column("request_id", sa.String(), nullable=True))
    op.create_index("uq_attempt_request", "attempts", ["workspace_id", "request_id"], unique=True)
    op.create_table("attempt_reviews",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id"), nullable=False),
                    sa.Column("score", sa.Float(), nullable=False),
                    sa.Column("feedback", sa.String(), nullable=False),
                    sa.Column("created_at", sa.String(), nullable=False))
    op.create_index("ix_attempt_reviews_attempt_id", "attempt_reviews", ["attempt_id"])
    op.create_table("study_tasks",
                    sa.Column("id", sa.String(), primary_key=True),
                    sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False),
                    sa.Column("title", sa.String(), nullable=False),
                    sa.Column("question_ids", sa.JSON(), nullable=False),
                    sa.Column("created_at", sa.String(), nullable=False))
    op.create_index("ix_study_tasks_workspace_id", "study_tasks", ["workspace_id"])


def downgrade():
    raise RuntimeError("Restore the migration backup; learning history must be preserved")
