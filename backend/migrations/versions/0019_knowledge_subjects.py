"""Workspace-owned knowledge subjects and their immutable revisions."""
import sqlalchemy as sa
from alembic import op

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('knowledge_subject_revisions',
        sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), primary_key=True),
        sa.Column('subject_id', sa.String(), primary_key=True),
        sa.Column('revision', sa.Integer(), primary_key=True),
        sa.Column('previous_revision', sa.Integer()),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'request_id'),
        sa.ForeignKeyConstraint(['workspace_id', 'subject_id', 'previous_revision'],
                                ['knowledge_subject_revisions.workspace_id', 'knowledge_subject_revisions.subject_id',
                                 'knowledge_subject_revisions.revision']),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 500"),
        sa.CheckConstraint("(revision=1 AND action='create' AND previous_revision IS NULL) OR "
                           "(revision>1 AND action IN ('rename','remove') AND previous_revision IS NOT NULL "
                           "AND previous_revision=revision-1)"))
    for operation in ('UPDATE', 'DELETE'):
        op.execute(f'CREATE TRIGGER knowledge_subjects_no_{operation.lower()} BEFORE {operation} '
                   "ON knowledge_subject_revisions BEGIN SELECT RAISE(ABORT, 'subject history is append only'); END")


def downgrade():
    raise RuntimeError('请从保留的迁移前备份恢复；知识点科目修订须保留')
