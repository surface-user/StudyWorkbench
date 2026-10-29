"""Preserve M0 records in a default workspace and add durable layouts."""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    workspaces = op.create_table(
        "workspaces", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("layout", sa.JSON(), nullable=False),
    )
    op.bulk_insert(workspaces, [{
        "id": "default", "name": "我的考研学习", "archived": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "layout": {"version": 1, "tabs": [{"id": "welcome", "kind": "question", "draft": ""}],
                   "closed_tabs": [], "active_tab_id": "welcome"},
    }])
    state = op.create_table(
        "desktop_state", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("active_workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False),
    )
    op.bulk_insert(state, [{"id": 1, "active_workspace_id": "default"}])
    op.create_table(
        "questions_v2", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("content", sa.JSON(), nullable=False),
    )
    op.create_table(
        "attempts_v2", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("question_id", sa.String(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id", "question_id"],
                                ["questions_v2.workspace_id", "questions_v2.id"]),
    )
    op.execute("INSERT INTO questions_v2 SELECT id, 'default', content FROM questions")
    op.execute("INSERT INTO attempts_v2 SELECT id, 'default', question_id, response, status, score, created_at FROM attempts")
    op.drop_table("attempts")
    op.drop_table("questions")
    op.rename_table("questions_v2", "questions")
    op.rename_table("attempts_v2", "attempts")
    op.create_index("ix_attempts_workspace_id", "attempts", ["workspace_id"])


def downgrade():
    # Dropping workspace ownership would discard/isolate records incorrectly.
    raise RuntimeError("Restore the pre-migration backup instead of discarding workspace data")
