"""Append learning annotations without rewriting attempts or confirmed content."""
import sqlalchemy as sa
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('learning_events',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('attempt_id', sa.Integer(), sa.ForeignKey('attempts.id'), nullable=False),
                    sa.Column('request_id', sa.String(), nullable=False),
                    sa.Column('content', sa.JSON(), nullable=False),
                    sa.Column('created_at', sa.String(), nullable=False),
                    sa.UniqueConstraint('attempt_id', 'request_id'))
    op.create_index('ix_learning_events_attempt', 'learning_events', ['attempt_id', 'id'])
    for action in ('UPDATE', 'DELETE'):
        op.execute(f"""CREATE TRIGGER learning_events_no_{action.lower()} BEFORE {action} ON learning_events
                       BEGIN SELECT RAISE(ABORT, 'learning events are append only'); END""")


def downgrade():
    raise RuntimeError('Restore the retained backup; never delete learning history')
