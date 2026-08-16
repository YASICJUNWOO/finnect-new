"""수집 건수 제한 기록

Revision ID: c95f819e9ac4
Revises: 5aa27e7f8582
Create Date: 2026-08-16 19:32:56.720207

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c95f819e9ac4"
down_revision: str | None = "5aa27e7f8582"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # item_limit 은 '요청한 건수', expected 는 '출처가 말한 전량'.
    # 둘이 있어야 맛보기 수집과 전량 수집이 건수만 보고도 구분된다.
    op.add_column("ingest_run", sa.Column("item_limit", sa.Integer(), nullable=True))
    op.add_column("ingest_run", sa.Column("expected", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ingest_run", "expected")
    op.drop_column("ingest_run", "item_limit")
