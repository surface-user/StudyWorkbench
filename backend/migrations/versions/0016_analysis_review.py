"""Persistent external analysis candidates and append-only review history, without a model."""
import sqlalchemy as sa
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('analysis_review_drafts',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('creation_content', sa.JSON(), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('payload_sha256', sa.String(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('adoption', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('rejection_reason', sa.String(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'request_id'),
        sa.CheckConstraint('revision >= 1'),
        sa.CheckConstraint("status IN ('pending','adopting','adopted','rejected','failed')"))
    op.create_index('ix_analysis_review_workspace', 'analysis_review_drafts', ['workspace_id', 'id'])
    op.create_table('analysis_review_revisions',
        sa.Column('draft_id', sa.String(), sa.ForeignKey('analysis_review_drafts.id'), primary_key=True),
        sa.Column('revision', sa.Integer(), primary_key=True),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False))
    for action in ['UPDATE', 'DELETE']:
        op.execute(f"CREATE TRIGGER protect_analysis_revision_{action.lower()} BEFORE {action} ON analysis_review_revisions BEGIN SELECT RAISE(ABORT, 'review history is append only'); END")


def downgrade():
    raise RuntimeError('审核草稿和修订不自动删除或降级；请从保留备份恢复')
