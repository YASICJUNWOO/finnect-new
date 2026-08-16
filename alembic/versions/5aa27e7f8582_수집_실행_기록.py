"""수집 실행 기록

Revision ID: 5aa27e7f8582
Revises: bb855b1f183f
Create Date: 2026-08-16 19:20:34.108241

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5aa27e7f8582"
down_revision: str | None = "bb855b1f183f"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ingest_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("only_open", sa.Boolean(), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("items", sa.Integer(), nullable=False),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("changed", sa.Integer(), nullable=False),
        sa.Column("unchanged", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("attachments", sa.Integer(), nullable=False),
        sa.Column("ratelimit_remaining", sa.Integer(), nullable=True),
        sa.Column("unknown_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingest_run_source_started", "ingest_run", ["source", "started_at"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ingest_run_source_started", table_name="ingest_run")
    op.drop_table("ingest_run")
