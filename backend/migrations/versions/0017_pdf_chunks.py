"""Durable page-range jobs for managed PDF resources."""
import sqlalchemy as sa
from alembic import op

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pdf_chunk_jobs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('resource_id', sa.String(), sa.ForeignKey('resources.id'), nullable=False),
        sa.Column('source_sha256', sa.String(), nullable=False),
        sa.Column('parser_version', sa.String(), nullable=False),
        sa.Column('first_page', sa.Integer(), nullable=False),
        sa.Column('last_page', sa.Integer(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=False),
        sa.Column('next_page', sa.Integer(), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('asset_bytes', sa.Integer(), nullable=False),
        sa.Column('question_count', sa.Integer(), nullable=False),
        sa.Column('material_count', sa.Integer(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'resource_id', 'source_sha256', 'parser_version',
                            'first_page', 'last_page'),
        sa.CheckConstraint('1 <= first_page AND first_page <= last_page AND last_page <= page_count '
                           'AND page_count <= 2000 AND last_page-first_page < 100 '
                           'AND next_page BETWEEN first_page AND last_page+1'),
        sa.CheckConstraint("status IN ('ready','running','cancelled','interrupted','failed','parsed')"),
        sa.CheckConstraint('generation >= 0 AND asset_bytes BETWEEN 0 AND 67108864 '
                           'AND question_count BETWEEN 0 AND 200 AND material_count BETWEEN 0 AND 200'))
    op.create_table('pdf_chunks',
        sa.Column('job_id', sa.String(), sa.ForeignKey('pdf_chunk_jobs.id'), primary_key=True),
        sa.Column('first_page', sa.Integer(), primary_key=True),
        sa.Column('last_page', sa.Integer(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.CheckConstraint('1 <= first_page AND first_page <= last_page AND last_page-first_page < 20'))


def downgrade():
    raise RuntimeError('分块解析进度和已提取结果不自动删除，请从保留的备份恢复')
