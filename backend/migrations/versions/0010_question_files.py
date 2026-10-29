"""Map explicit question files and append immutable confirmed versions; retain old attempts."""
import sqlalchemy as sa
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('question_files',
                    sa.Column('workspace_id', sa.String(), primary_key=True),
                    sa.Column('question_id', sa.String(), primary_key=True),
                    sa.Column('node_id', sa.String(), nullable=False),
                    sa.Column('origin_kind', sa.String(), nullable=False),
                    sa.Column('origin_id', sa.String(), nullable=False),
                    sa.Column('confirmed_version_id', sa.String(), nullable=True),
                    sa.ForeignKeyConstraint(['workspace_id', 'node_id'],
                                            ['workspace_nodes.workspace_id', 'workspace_nodes.id']),
                    sa.ForeignKeyConstraint(['confirmed_version_id'], ['question_versions.id']),
                    sa.UniqueConstraint('workspace_id', 'node_id'))
    op.create_table('question_versions',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('workspace_id', sa.String(), nullable=False),
                    sa.Column('question_id', sa.String(), nullable=False),
                    sa.Column('revision', sa.Integer(), nullable=False),
                    sa.Column('markdown_sha256', sa.String(), nullable=False),
                    sa.Column('content_sha256', sa.String(), nullable=False),
                    sa.Column('relative_path', sa.String(), nullable=False),
                    sa.Column('content', sa.JSON(), nullable=False),
                    sa.Column('attachments', sa.JSON(), nullable=False),
                    sa.Column('created_at', sa.String(), nullable=False),
                    sa.ForeignKeyConstraint(['workspace_id', 'question_id'],
                                            ['question_files.workspace_id', 'question_files.question_id']),
                    sa.ForeignKeyConstraint(['workspace_id', 'question_id'], ['questions.workspace_id', 'questions.id']),
                    sa.UniqueConstraint('workspace_id', 'question_id', 'revision'),
                    sa.CheckConstraint('revision >= 1'))
    op.add_column('attempts', sa.Column('question_version_id', sa.String(), nullable=True))
    op.create_index('ix_attempts_question_version', 'attempts', ['question_version_id'])
    for operation in ['UPDATE', 'DELETE']:
        op.execute(f"""CREATE TRIGGER question_versions_no_{operation.lower()} BEFORE {operation} ON question_versions
                       BEGIN SELECT RAISE(ABORT, 'confirmed question versions are immutable'); END""")
    for operation in ['INSERT', 'UPDATE']:
        op.execute(f"""CREATE TRIGGER question_files_version_scope_{operation.lower()} BEFORE {operation} ON question_files
                       WHEN NEW.confirmed_version_id IS NOT NULL AND NOT EXISTS
                         (SELECT 1 FROM question_versions WHERE id=NEW.confirmed_version_id
                          AND workspace_id=NEW.workspace_id AND question_id=NEW.question_id)
                       BEGIN SELECT RAISE(ABORT, 'confirmed version scope mismatch'); END""")
        op.execute(f"""CREATE TRIGGER attempts_version_scope_{operation.lower()} BEFORE {operation} ON attempts
                       WHEN NEW.question_version_id IS NOT NULL AND NOT EXISTS
                         (SELECT 1 FROM question_versions WHERE id=NEW.question_version_id
                          AND workspace_id=NEW.workspace_id AND question_id=NEW.question_id)
                       BEGIN SELECT RAISE(ABORT, 'attempt version scope mismatch'); END""")
    op.execute("""CREATE TRIGGER attempts_version_binding_immutable BEFORE UPDATE OF question_version_id ON attempts
                  WHEN OLD.question_version_id IS NOT NEW.question_version_id
                  BEGIN SELECT RAISE(ABORT, 'attempt version binding is immutable'); END""")


def downgrade():
    raise RuntimeError('Restore the preserved database/files backup; never discard confirmed versions or history')
