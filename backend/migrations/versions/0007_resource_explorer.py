"""Add a managed logical resource tree without rewriting learning data or files."""
import re
import unicodedata
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('resources', 'media_entries'):
        op.create_index(f'ux_{table}_workspace_id', table, ['workspace_id', 'id'], unique=True)
    op.create_table('workspace_nodes',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
                    sa.Column('parent_id', sa.String(), nullable=True),
                    sa.Column('kind', sa.String(), nullable=False),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.Column('name_key', sa.String(), nullable=False),
                    sa.Column('resource_id', sa.String(), nullable=True),
                    sa.Column('media_id', sa.String(), nullable=True),
                    sa.Column('url', sa.String(), nullable=True),
                    sa.UniqueConstraint('workspace_id', 'id'),
                    sa.ForeignKeyConstraint(['workspace_id', 'parent_id'],
                                            ['workspace_nodes.workspace_id', 'workspace_nodes.id']),
                    sa.ForeignKeyConstraint(['workspace_id', 'resource_id'], ['resources.workspace_id', 'resources.id']),
                    sa.ForeignKeyConstraint(['workspace_id', 'media_id'], ['media_entries.workspace_id', 'media_entries.id']),
                    sa.CheckConstraint("parent_id IS NULL OR parent_id != id"),
                    sa.CheckConstraint("(kind='folder' AND resource_id IS NULL AND media_id IS NULL AND url IS NULL) OR "
                                       "(kind='resource' AND resource_id IS NOT NULL AND media_id IS NULL AND url IS NULL) OR "
                                       "(kind='media' AND media_id IS NOT NULL AND resource_id IS NULL AND url IS NULL) OR "
                                       "(kind='link' AND url IS NOT NULL AND resource_id IS NULL AND media_id IS NULL)"))
    op.execute("CREATE UNIQUE INDEX ux_nodes_sibling_name ON workspace_nodes "
               "(workspace_id, coalesce(parent_id, ''), name_key)")
    op.create_table('resource_add_jobs',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('workspace_id', sa.String(), sa.ForeignKey('workspaces.id'), nullable=False),
                    sa.Column('parent_id', sa.String(), nullable=True),
                    sa.Column('source_path', sa.String(), nullable=False),
                    sa.Column('status', sa.String(), nullable=False),
                    sa.Column('cancel_requested', sa.Boolean(), nullable=False),
                    sa.Column('results', sa.JSON(), nullable=False),
                    sa.Column('error', sa.String(), nullable=True),
                    sa.ForeignKeyConstraint(['workspace_id', 'parent_id'],
                                            ['workspace_nodes.workspace_id', 'workspace_nodes.id']))
    connection = op.get_bind()
    names = {}
    for table, label, kind, payload in [('resources', 'original_name', 'resource', 'resource_id'),
                                       ('media_entries', 'title', 'media', 'media_id')]:
        for row in connection.execute(sa.text(f'SELECT id, workspace_id, {label} FROM {table} ORDER BY id')):
            # Preserve original metadata; only the new display name is sanitized.
            name = unicodedata.normalize('NFC', re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', row[2]))[:180].rstrip(' .') or '资源'
            if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', name):
                name = '_' + name
            used = names.setdefault(row[1], set())
            candidate, number = name, 2
            while candidate.casefold() in used:
                candidate = f'{name} ({number})'
                number += 1
            used.add(candidate.casefold())
            connection.execute(sa.text(f'INSERT INTO workspace_nodes '
                               f'(id,workspace_id,kind,name,name_key,{payload}) VALUES (:id,:ws,:kind,:name,:key,:target)'),
                               dict(id=uuid4().hex, ws=row[1], kind=kind, name=candidate,
                                    key=candidate.casefold(), target=row[0]))


def downgrade():
    raise RuntimeError('Restore the preserved migration backup; do not discard resource identities')
