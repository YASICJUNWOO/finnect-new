"""양식 칸의 좌표를 항목에 심는다

`document_item.anchor` 하나를 더한다 — `"구역:표:행:열"`(`forms.Anchor`).

**자동 생성이 더 잡은 것을 지웠다.** `attachment` 컬럼 일곱과 `wiki_fact.kind`
의 NULL 허용은 **다른 작업의 것**이고, 여기 섞으면 그 작업이 자기 마이그레이션을
쓸 때 부딪힌다. 한 마이그레이션은 한 결정만 담는다.

Revision ID: 129eaa00e5ee
Revises: d9a4e17c6b52
Create Date: 2026-08-23 15:32:16.645600

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '129eaa00e5ee'
down_revision: Union[str, Sequence[str], None] = 'd9a4e17c6b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('document_item', sa.Column('anchor', sa.String(length=32), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_item', 'anchor')
