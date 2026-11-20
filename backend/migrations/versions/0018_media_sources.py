"""Typed local media sources and execution receipts; legacy URLs and rows are retained."""
import sqlalchemy as sa
from alembic import op

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite batch recreation does not retain unnamed CHECKs automatically.
    checks = (
        sa.CheckConstraint("status IN ('queued','running','paused','interrupted','failed','ready')",
                           name='ck_download_status'),
        sa.CheckConstraint('attempt >= 1', name='ck_download_attempt'),
    )
    with op.batch_alter_table('media_download_jobs', recreate='always', table_args=checks,
                              reflect_kwargs={'resolve_fks': False}) as batch:
        batch.alter_column('source_url', existing_type=sa.String(), nullable=True)
        batch.add_column(sa.Column('source_kind', sa.String(), nullable=False, server_default='direct_https'))
        batch.add_column(sa.Column('source_snapshot', sa.JSON(none_as_null=True), nullable=True))
        batch.add_column(sa.Column('source_snapshot_sha256', sa.String(), nullable=True))
        batch.add_column(sa.Column('run_generation', sa.Integer(), nullable=False, server_default='0'))
        batch.create_unique_constraint('uq_download_job_workspace', ['id', 'workspace_id'])
        batch.create_check_constraint('ck_download_generation', 'run_generation >= 0')
        batch.create_check_constraint('ck_download_source',
            "(source_kind='direct_https' AND source_url IS NOT NULL AND source_snapshot IS NULL "
            "AND source_snapshot_sha256 IS NULL) OR "
            "(source_kind='local_pair' AND source_url IS NULL AND source_snapshot IS NOT NULL "
            "AND length(source_snapshot) BETWEEN 1 AND 16384 AND source_snapshot_sha256 IS NOT NULL "
            "AND length(source_snapshot_sha256)=64 AND source_snapshot_sha256 NOT GLOB '*[^0-9a-f]*')")
    op.create_table('media_download_attempts',
        sa.Column('job_id', sa.String(), primary_key=True),
        sa.Column('generation', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('source_snapshot_sha256', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('phase', sa.String(), nullable=False),
        sa.Column('record', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['job_id', 'workspace_id'], ['media_download_jobs.id', 'media_download_jobs.workspace_id']),
        sa.CheckConstraint('attempt >= 1 AND generation >= 1'),
        sa.CheckConstraint("status IN ('running','paused','interrupted','failed','ready')"),
        sa.CheckConstraint("phase IN ('copying','probing','muxing','validating','publishing','ready')"),
        sa.CheckConstraint("(status='ready')=(phase='ready')"),
        sa.CheckConstraint('length(record) BETWEEN 1 AND 8192'),
        sa.CheckConstraint("length(source_snapshot_sha256)=64 AND source_snapshot_sha256 NOT GLOB '*[^0-9a-f]*'"))
    op.execute("""CREATE TRIGGER immutable_media_download_source
        BEFORE UPDATE OF source_kind,source_url,source_snapshot,source_snapshot_sha256 ON media_download_jobs
        BEGIN SELECT RAISE(ABORT, 'media download source is immutable'); END""")


def downgrade():
    raise RuntimeError('媒体来源与执行收据不自动删除，请从保留备份恢复')
