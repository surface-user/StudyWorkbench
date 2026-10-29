"""Record optional Office conversions and derived PDF provenance without rewriting originals."""
import sqlalchemy as sa
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('document_previews',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('workspace_id', sa.String(), nullable=False),
                    sa.Column('node_id', sa.String(), nullable=False),
                    sa.Column('source_resource_id', sa.String(), nullable=False),
                    sa.Column('source_sha256', sa.String(), nullable=False),
                    sa.Column('runtime_fingerprint', sa.String(), nullable=False),
                    sa.Column('converter_version', sa.String(), nullable=False),
                    sa.Column('options_hash', sa.String(), nullable=False),
                    sa.Column('status', sa.String(), nullable=False),
                    sa.Column('cancel_requested', sa.Boolean(), nullable=False),
                    sa.Column('relative_pdf', sa.String(), nullable=False),
                    sa.Column('pdf_sha256', sa.String(), nullable=True),
                    sa.Column('pdf_size', sa.Integer(), nullable=True),
                    sa.Column('page_count', sa.Integer(), nullable=True),
                    sa.Column('error', sa.String(), nullable=True),
                    sa.Column('created_at', sa.String(), nullable=False),
                    sa.ForeignKeyConstraint(['workspace_id', 'node_id'],
                                            ['workspace_nodes.workspace_id', 'workspace_nodes.id']),
                    sa.ForeignKeyConstraint(['workspace_id', 'source_resource_id'],
                                            ['resources.workspace_id', 'resources.id']))
    op.create_index('ix_document_previews_node', 'document_previews', ['workspace_id', 'node_id', 'created_at'])
    op.create_index('ix_document_previews_status', 'document_previews', ['status'])


def downgrade():
    raise RuntimeError('Restore the preserved backup and files; never discard preview provenance')
