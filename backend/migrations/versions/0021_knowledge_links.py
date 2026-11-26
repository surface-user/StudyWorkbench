"""Typed workspace-local knowledge links and their removal receipts."""
import sqlalchemy as sa
from alembic import op

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade():
    point = ['knowledge_point_revisions.workspace_id', 'knowledge_point_revisions.subject_id',
             'knowledge_point_revisions.point_id', 'knowledge_point_revisions.revision']
    op.create_table(
        'knowledge_link_revisions',
        sa.Column('workspace_id', sa.String(), primary_key=True),
        sa.Column('link_id', sa.String(), primary_key=True),
        sa.Column('revision', sa.Integer(), primary_key=True),
        sa.Column('previous_revision', sa.Integer()),
        sa.Column('first_revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('subject_id', sa.String(), nullable=False),
        sa.Column('point_id', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('label', sa.String()),
        sa.Column('target_subject_id', sa.String()),
        sa.Column('target_point_id', sa.String()),
        sa.Column('node_id', sa.String()),
        sa.Column('question_id', sa.String()),
        sa.UniqueConstraint('workspace_id', 'request_id'),
        sa.ForeignKeyConstraint(['workspace_id', 'link_id', 'previous_revision'],
                                ['knowledge_link_revisions.workspace_id', 'knowledge_link_revisions.link_id',
                                 'knowledge_link_revisions.revision']),
        sa.ForeignKeyConstraint(['workspace_id', 'subject_id', 'point_id', 'first_revision'], point),
        sa.ForeignKeyConstraint(['workspace_id', 'target_subject_id', 'target_point_id', 'first_revision'], point),
        sa.ForeignKeyConstraint(['workspace_id', 'node_id'], ['workspace_nodes.workspace_id', 'workspace_nodes.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'question_id'], ['questions.workspace_id', 'questions.id']),
        sa.CheckConstraint('first_revision=1 AND ((revision=1 AND previous_revision IS NULL) OR '
                           '(revision=2 AND previous_revision IS NOT NULL AND previous_revision=1))'),
        sa.CheckConstraint("""(kind IN ('related','directed') AND target_subject_id IS NOT NULL
                               AND target_point_id IS NOT NULL AND node_id IS NULL AND question_id IS NULL
                               AND (subject_id,point_id)!=(target_subject_id,target_point_id))
                           OR (kind='resource' AND node_id IS NOT NULL AND question_id IS NULL
                               AND target_subject_id IS NULL AND target_point_id IS NULL)
                           OR (kind='question' AND question_id IS NOT NULL AND node_id IS NULL
                               AND target_subject_id IS NULL AND target_point_id IS NULL)"""),
        sa.CheckConstraint("(kind='directed' AND label IS NOT NULL AND length(label) BETWEEN 1 AND 500) "
                           "OR (kind!='directed' AND label IS NULL)"),
        sa.CheckConstraint("kind!='related' OR (subject_id, point_id)<(target_subject_id,target_point_id)"),
    )
    for verb in ('UPDATE', 'DELETE'):
        op.execute(f'CREATE TRIGGER knowledge_links_no_{verb.lower()} BEFORE {verb} ON knowledge_link_revisions '
                   "BEGIN SELECT RAISE(ABORT, 'knowledge link history is append only'); END")


def downgrade():
    raise RuntimeError('请从保留的迁移前备份恢复；知识关联修订须保留')
