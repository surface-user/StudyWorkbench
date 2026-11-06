"""Versioned learning marks and scoped note relationships, retaining all old records."""
import sqlalchemy as sa
from alembic import op

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ux_notes_workspace_id', 'notes', ['workspace_id', 'id'], unique=True)
    op.create_table('learning_marks',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('resource_item_id', sa.String(), nullable=False),
        sa.Column('anchor', sa.JSON(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('note', sa.String(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('creation_content', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('updated_at', sa.String(), nullable=False),
        sa.Column('removed_at', sa.String(), nullable=True),
        sa.UniqueConstraint('workspace_id', 'id'),
        sa.UniqueConstraint('workspace_id', 'request_id'),
        sa.CheckConstraint('revision >= 1'),
        sa.ForeignKeyConstraint(['workspace_id', 'resource_item_id'], ['workspace_nodes.workspace_id', 'workspace_nodes.id']))
    op.create_index('ix_learning_marks_node', 'learning_marks', ['workspace_id', 'resource_item_id', 'id'])
    op.create_table('learning_mark_revisions',
        sa.Column('mark_id', sa.String(), sa.ForeignKey('learning_marks.id'), primary_key=True),
        sa.Column('revision', sa.Integer(), primary_key=True),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False))
    op.create_table('learning_mark_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('mark_id', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('file_node_id', sa.String(), nullable=True),
        sa.Column('legacy_note_id', sa.String(), nullable=True),
        sa.UniqueConstraint('mark_id', 'file_node_id'),
        sa.UniqueConstraint('mark_id', 'legacy_note_id'),
        sa.ForeignKeyConstraint(['workspace_id', 'mark_id'], ['learning_marks.workspace_id', 'learning_marks.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'file_node_id'], ['workspace_nodes.workspace_id', 'workspace_nodes.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'legacy_note_id'], ['notes.workspace_id', 'notes.id']),
        sa.CheckConstraint("(kind='file_note' AND file_node_id IS NOT NULL AND legacy_note_id IS NULL) OR "
                           "(kind='legacy_note' AND legacy_note_id IS NOT NULL AND file_node_id IS NULL)"))
    for action in ('UPDATE', 'DELETE'):
        op.execute(f"CREATE TRIGGER mark_revisions_no_{action.lower()} BEFORE {action} ON learning_mark_revisions "
                   "BEGIN SELECT RAISE(ABORT, 'Learning mark history is immutable'); END")
    op.execute("CREATE TRIGGER marks_no_delete BEFORE DELETE ON learning_marks "
               "BEGIN SELECT RAISE(ABORT, 'Remove learning marks with a tombstone'); END")


def downgrade():
    raise RuntimeError('Restore the preserved backup; do not discard learning marks or history')
