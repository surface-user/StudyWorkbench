"""Persistent scoped direct-media downloads; never removes prior learning data."""
import sqlalchemy as sa
from alembic import op

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('media_download_jobs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('parent_id', sa.String(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('source_url', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('cancel_requested', sa.Boolean(), nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('relative_path', sa.String(), nullable=False),
        sa.Column('progress', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'request_id'),
        sa.CheckConstraint("status IN ('queued','running','paused','interrupted','failed','ready')"),
        sa.CheckConstraint('attempt >= 1'),
        sa.ForeignKeyConstraint(['workspace_id', 'parent_id'], ['workspace_nodes.workspace_id', 'workspace_nodes.id']))
    op.create_index('ix_download_workspace', 'media_download_jobs', ['workspace_id', 'id'])


def downgrade():
    raise RuntimeError('下载任务迁移不自动降级或删除已保存数据；请从保留备份恢复')
