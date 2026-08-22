"""draft_item.edited_body · edited_at — 사람이 고친 글

Revision ID: 4c1f7a92be08
Revises: 15706a31ec2f
Create Date: 2026-08-22 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c1f7a92be08'
down_revision: Union[str, Sequence[str], None] = '15706a31ec2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """`body` 옆에 둔다. **덮어쓰지 않는다**(ADR-0055 · plan/21 T-0123).

    `body` 는 집필기의 것이고 이쪽이 사람의 것이다. 한 칸에 섞으면 되돌릴 자리가
    없어지고, `draft_evidence` 의 문단 번호가 사람 편집을 따라 어긋난다.

    **`NULL` 과 빈 문자열이 다르다.** 앞은 안 고친 것이고 뒤는 일부러 비운 것이다 —
    `server_default` 를 주지 않는 이유가 그것이다. 기존 행은 전부 `NULL` 로 앉아
    「안 고쳤다」가 된다.
    """
    op.add_column("draft_item", sa.Column("edited_body", sa.Text(), nullable=True))
    op.add_column(
        "draft_item",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """**사람이 쓴 글이 사라진다.** 되돌리기 전에 옮겨 둘 것."""
    op.drop_column("draft_item", "edited_at")
    op.drop_column("draft_item", "edited_body")
