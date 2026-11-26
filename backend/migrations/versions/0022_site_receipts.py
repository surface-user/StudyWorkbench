"""Keep confirmed site metadata with the direct transfer, without storing its temporary signed URL."""
import sqlalchemy as sa
from alembic import op

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('media_download_jobs', sa.Column('site_receipt', sa.JSON(none_as_null=True), nullable=True))
    op.execute("""CREATE UNIQUE INDEX uq_site_preview_format ON media_download_jobs
                  (workspace_id, json_extract(site_receipt, '$.preview_id'), json_extract(site_receipt, '$.format_id'))
                  WHERE site_receipt IS NOT NULL""")
    op.execute("""CREATE TRIGGER immutable_site_receipt BEFORE UPDATE OF site_receipt ON media_download_jobs
                  WHEN NEW.site_receipt IS NOT OLD.site_receipt
                  BEGIN SELECT RAISE(ABORT, 'immutable site receipt'); END""")


def downgrade():
    raise RuntimeError('禁止自动降级个人学习数据')
