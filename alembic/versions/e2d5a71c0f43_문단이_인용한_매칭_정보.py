"""문단이 인용한 매칭 정보 — plan/22 T-0134

`draft_evidence` 를 그대로 베낀 표 하나. `fact_id` 자리에 `value_id` 가 온다.

트랙이 갈리면서 집필 재료가 표 둘에서 오는데(`wiki_fact` · `company_value`) 근거를
적을 자리는 하나뿐이었다 — `draft_evidence.fact_id` 가 `wiki_fact.id` 를 NOT NULL 로
든다. 그래서 문단이 직원 수를 인용해도 **어디에도 안 남았다.**

**표를 나눈 이유는 ADR-0056 이 `wiki_evidence`/`value_evidence` 를 나눌 때와 같다** —
한 표에 nullable 둘을 두면 모든 조인이 「둘 중 어느 쪽인가」를 물어야 한다.

**옮길 데이터가 없다.** 이 표가 없던 동안 값을 인용한 문단이 아예 없었다(재료에
안 들어갔다). 표만 세우면 된다.

Revision ID: e2d5a71c0f43
Revises: c7f2a91b4d38
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2d5a71c0f43"
down_revision: str | Sequence[str] | None = "c7f2a91b4d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft_value_evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("draft_item_id", sa.BigInteger(), nullable=False),
        sa.Column("paragraph", sa.Integer(), nullable=False),
        sa.Column("value_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=True),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["draft_item_id"], ["draft_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["value_id"], ["company_value.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunk.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_item_id", "paragraph", "value_id", name="uq_draft_value_evidence_para_value"
        ),
    )
    op.create_index(
        op.f("ix_draft_value_evidence_draft_item_id"),
        "draft_value_evidence",
        ["draft_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_draft_value_evidence_chunk", "draft_value_evidence", ["chunk_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_draft_value_evidence_chunk", table_name="draft_value_evidence")
    op.drop_index(
        op.f("ix_draft_value_evidence_draft_item_id"), table_name="draft_value_evidence"
    )
    op.drop_table("draft_value_evidence")
