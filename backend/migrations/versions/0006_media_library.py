"""Workspace local-media index and playback state; files stay in the data directory."""
import sqlalchemy as sa
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('media_entries',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
                    sa.Column('title', sa.String(), nullable=False),
                    sa.Column('relative_path', sa.String(), nullable=False),
                    sa.Column('mime', sa.String(), nullable=False),
                    sa.Column('size', sa.Integer(), nullable=False),
                    sa.Column('sha256', sa.String(), nullable=False),
                    sa.Column('status', sa.String(), nullable=False),
                    sa.Column('playback', sa.JSON(), nullable=False))
    op.create_index('ix_media_entries_workspace_id', 'media_entries', ['workspace_id'])


def downgrade():
    raise RuntimeError('Restore the migration backup; media and playback state must be preserved')
