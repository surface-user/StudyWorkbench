"""Independent Markdown questions extracted from user documents, with no required answer."""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('markdown_questions',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
                    sa.Column('import_job_id', sa.String(), sa.ForeignKey('import_jobs.id'), nullable=False),
                    sa.Column('ordinal', sa.Integer(), nullable=False),
                    sa.Column('source_resource_id', sa.String(), sa.ForeignKey('resources.id'), nullable=False),
                    sa.Column('markdown_resource_id', sa.String(), sa.ForeignKey('resources.id'), nullable=False),
                    sa.Column('title', sa.String(), nullable=False),
                    sa.Column('content', sa.JSON(), nullable=False),
                    sa.UniqueConstraint('import_job_id', 'ordinal', name='uq_markdown_question_ordinal'))
    op.create_index('ix_markdown_questions_workspace_id', 'markdown_questions', ['workspace_id'])
    op.create_index('ix_markdown_questions_import_job_id', 'markdown_questions', ['import_job_id'])


def downgrade():
    raise RuntimeError('Restore the migration backup; question files must be preserved')
