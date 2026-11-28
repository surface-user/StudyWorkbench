"""Keep a confirmed site pair and its attempts in the existing download queue."""
from alembic import op

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite cannot edit a CHECK in place. Rebuild the two triggers and the expression index
    # that table reflection cannot reproduce, including the pre-existing single-file receipt.
    op.execute('DROP INDEX uq_site_preview_format')
    # The child FK is immediate: retain every execution row in this same DDL transaction
    # while its referenced table is replaced. Keep foreign-key enforcement enabled.
    op.execute('CREATE TEMP TABLE retained_0023_attempts AS SELECT * FROM media_download_attempts')
    op.execute('DELETE FROM media_download_attempts')
    with op.batch_alter_table('media_download_jobs', recreate='always',
                              reflect_kwargs={'resolve_fks': False}) as batch:
        batch.drop_constraint('ck_download_source', type_='check')
        batch.create_check_constraint('ck_download_source',
            "(source_kind='direct_https' AND source_url IS NOT NULL AND source_snapshot IS NULL "
            "AND source_snapshot_sha256 IS NULL) OR "
            "(source_kind IN ('local_pair','site_pair') AND source_url IS NULL AND site_receipt IS NULL "
            "AND source_snapshot IS NOT NULL AND length(source_snapshot) BETWEEN 1 AND 16384 "
            "AND source_snapshot_sha256 IS NOT NULL AND length(source_snapshot_sha256)=64 "
            "AND source_snapshot_sha256 NOT GLOB '*[^0-9a-f]*')")
    op.execute('INSERT INTO media_download_attempts SELECT * FROM temp.retained_0023_attempts')
    op.execute('DROP TABLE temp.retained_0023_attempts')
    op.execute("""CREATE TRIGGER immutable_media_download_source
        BEFORE UPDATE OF source_kind,source_url,source_snapshot,source_snapshot_sha256 ON media_download_jobs
        BEGIN SELECT RAISE(ABORT, 'media download source is immutable'); END""")
    op.execute("""CREATE TRIGGER immutable_site_receipt BEFORE UPDATE OF site_receipt ON media_download_jobs
                  WHEN NEW.site_receipt IS NOT OLD.site_receipt
                  BEGIN SELECT RAISE(ABORT, 'immutable site receipt'); END""")
    op.execute("""CREATE UNIQUE INDEX uq_site_preview_format ON media_download_jobs
                  (workspace_id, json_extract(site_receipt, '$.preview_id'), json_extract(site_receipt, '$.format_id'))
                  WHERE site_receipt IS NOT NULL""")
    op.execute("""CREATE UNIQUE INDEX uq_site_pair_preview ON media_download_jobs
                  (workspace_id, json_extract(source_snapshot, '$.preview_id')) WHERE source_kind='site_pair'""")


def downgrade():
    raise RuntimeError('禁止自动降级个人学习数据')
