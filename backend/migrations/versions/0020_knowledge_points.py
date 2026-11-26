"""Keep the history of the user's knowledge point tree."""
import sqlalchemy as sa
from alembic import op

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade():
    point_revision = ['knowledge_point_revisions.workspace_id', 'knowledge_point_revisions.subject_id',
                      'knowledge_point_revisions.point_id', 'knowledge_point_revisions.revision']
    op.create_table(
        'knowledge_point_revisions',
        sa.Column('workspace_id', sa.String(), primary_key=True),
        sa.Column('subject_id', sa.String(), primary_key=True),
        sa.Column('point_id', sa.String(), primary_key=True),
        sa.Column('revision', sa.Integer(), primary_key=True),
        sa.Column('previous_revision', sa.Integer()),
        sa.Column('first_revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_id', sa.String()),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'request_id'),
        sa.ForeignKeyConstraint(['workspace_id', 'subject_id', 'first_revision'],
                                ['knowledge_subject_revisions.workspace_id', 'knowledge_subject_revisions.subject_id',
                                 'knowledge_subject_revisions.revision']),
        sa.CheckConstraint('first_revision = 1 AND length(name) BETWEEN 1 AND 500'),
        sa.CheckConstraint('parent_id IS NULL OR parent_id != point_id'),
        sa.CheckConstraint("(revision = 1 AND previous_revision IS NULL AND action = 'create') OR "
                           "(revision > 1 AND previous_revision IS NOT NULL AND previous_revision = revision-1 "
                           "AND action IN ('rename', 'move', 'remove'))"),
        sa.ForeignKeyConstraint(['workspace_id', 'subject_id', 'point_id', 'previous_revision'], point_revision),
        sa.ForeignKeyConstraint(['workspace_id', 'subject_id', 'parent_id', 'first_revision'], point_revision),
    )
    for verb in ('UPDATE', 'DELETE'):
        op.execute(f'CREATE TRIGGER knowledge_points_no_{verb.lower()} BEFORE {verb} ON knowledge_point_revisions '
                   "BEGIN SELECT RAISE(ABORT, 'knowledge point history is append only'); END")


def downgrade():
    raise RuntimeError('请从保留的迁移前备份恢复；知识点修订须保留')
