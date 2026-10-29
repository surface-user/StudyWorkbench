"""Remove resources from the tree while retaining files and learning relations."""
import sqlalchemy as sa
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('workspace_nodes', sa.Column('removed_at', sa.String(), nullable=True))
    op.drop_index('ux_nodes_sibling_name', table_name='workspace_nodes')
    op.execute("CREATE UNIQUE INDEX ux_nodes_sibling_name ON workspace_nodes "
               "(workspace_id, coalesce(parent_id, ''), name_key) WHERE removed_at IS NULL")


def downgrade():
    raise RuntimeError('Restore the preserved migration backup; do not discard resource identities')
