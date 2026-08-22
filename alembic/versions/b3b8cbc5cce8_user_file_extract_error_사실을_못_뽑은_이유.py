"""user_file.extract_error — 사실을 못 뽑은 이유

Revision ID: b3b8cbc5cce8
Revises: 7349b82a6e6e
Create Date: 2026-08-22 09:26:13.275169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3b8cbc5cce8'
down_revision: Union[str, Sequence[str], None] = '7349b82a6e6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """`parse_error` 와 나란히 둔다. 다른 단계라 한 컬럼에 섞지 않는다(plan/12 T-0093)."""
    op.add_column("user_file", sa.Column("extract_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_file", "extract_error")
