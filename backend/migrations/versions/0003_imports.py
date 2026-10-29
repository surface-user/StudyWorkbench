"""Keep import originals and previews separate from confirmed learning data."""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resources", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("original_name", sa.String(), nullable=False),
        sa.Column("relative_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False), sa.Column("mime", sa.String(), nullable=False),
        sa.UniqueConstraint("workspace_id", "sha256", name="uq_resource_workspace_hash"),
    )
    op.create_index("ix_resources_workspace_id", "resources", ["workspace_id"])
    op.create_table(
        "import_jobs", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("resource_id", sa.String(), sa.ForeignKey("resources.id"), nullable=False),
        sa.Column("parser_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False), sa.Column("error", sa.String(), nullable=True),
        sa.Column("preview", sa.JSON(), nullable=False), sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_import_jobs_workspace_id", "import_jobs", ["workspace_id"])
    op.create_table(
        "passages", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("content", sa.JSON(), nullable=False),
    )
    op.create_table(
        "notes", sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("resource_id", sa.String(), sa.ForeignKey("resources.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False), sa.Column("content", sa.JSON(), nullable=False),
    )
    op.create_index("ix_notes_workspace_id", "notes", ["workspace_id"])


def downgrade():
    raise RuntimeError("Restore the pre-migration backup; import originals must be preserved")
