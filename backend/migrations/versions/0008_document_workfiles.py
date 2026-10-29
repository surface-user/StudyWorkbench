"""Keep editable Markdown and recoverable save receipts separate from immutable originals."""
import sqlalchemy as sa
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('document_workfiles',
                    sa.Column('node_id', sa.String(), primary_key=True),
                    sa.Column('workspace_id', sa.String(), nullable=False),
                    sa.Column('relative_path', sa.String(), nullable=False, unique=True),
                    sa.Column('indexed_sha256', sa.String(), nullable=False),
                    sa.ForeignKeyConstraint(['workspace_id', 'node_id'],
                                            ['workspace_nodes.workspace_id', 'workspace_nodes.id']))
    op.create_table('document_saves',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('node_id', sa.String(), sa.ForeignKey('document_workfiles.node_id'), nullable=False),
                    sa.Column('old_sha256', sa.String(), nullable=False),
                    sa.Column('new_sha256', sa.String(), nullable=False),
                    sa.Column('backup_path', sa.String(), nullable=False),
                    sa.Column('pending_path', sa.String(), nullable=False),
                    sa.Column('status', sa.String(), nullable=False))
    op.create_index('ix_document_saves_status', 'document_saves', ['status'])


def downgrade():
    raise RuntimeError('Restore the preserved backup and files; never discard working documents')
