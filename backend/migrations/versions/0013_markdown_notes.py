"""Durable creation receipts; leave existing notes, nodes and learning records unchanged."""
import sqlalchemy as sa
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('markdown_note_creations',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
                    sa.Column('request_id', sa.String(), nullable=False),
                    sa.Column('request', sa.JSON(), nullable=False),
                    sa.Column('resource_id', sa.String(), nullable=False),
                    sa.Column('status', sa.String(), nullable=False),
                    sa.Column('error', sa.String(), nullable=True),
                    sa.UniqueConstraint('workspace_id', 'request_id'),
                    sa.CheckConstraint("status IN ('prepared','ready','interrupted','conflict')"))


def downgrade():
    raise RuntimeError('Restore the preserved backup; do not discard note creation receipts')
