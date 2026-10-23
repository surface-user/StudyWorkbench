"""M0 question and attempt schema."""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("questions", sa.Column("id", sa.String(), primary_key=True),
                    sa.Column("content", sa.JSON(), nullable=False))
    op.create_table("attempts", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("question_id", sa.String(), sa.ForeignKey("questions.id"), nullable=False),
                    sa.Column("response", sa.JSON(), nullable=False),
                    sa.Column("status", sa.String(), nullable=False),
                    sa.Column("score", sa.Float(), nullable=True),
                    sa.Column("created_at", sa.String(), nullable=False))


def downgrade():
    op.drop_table("attempts")
    op.drop_table("questions")
