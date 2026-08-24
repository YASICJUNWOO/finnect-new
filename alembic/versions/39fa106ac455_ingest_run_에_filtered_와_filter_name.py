"""ingest_run 에 filtered 와 filter_name

적재에서 **우리가 빼기로 한 것**을 세고, 어느 정책으로 뺐는지 남긴다.

`skipped` 와 섞지 않는다 — 저기는 외부 ID 가 없어 못 넣은 **사고**이고 이쪽은 안 받기로
한 **정책**이다. 한 숫자로 세면 그 수가 늘었을 때 API 가 깨진 건지 우리가 거른 건지
구분이 안 된다.

`filter_name` 이 따로 있는 이유는 `only_open` 과 같다. 건수만 남기면 나중에
「이 코퍼스가 왜 이 크기지」를 못 푼다.

---
**자동 생성이 낸 것 중 아홉을 뺐다.** `attachment` 의 컬럼 일곱(`fetch_error`·`byte_size`·
`fetched_at`·`content_sha256`·`fetch_status`·`local_path`·`sniff_mismatch`)과 인덱스 둘을
지우자고 했고, `wiki_fact.kind` 를 nullable 로 바꾸자고 했다. **전부 이 변경과 무관한
기존 드리프트다** — 모델에는 없고 DB 에만 남아 있는 것들이라, 여기 끼워 넣으면 관계없는
컬럼이 이 마이그레이션에 묻어서 사라진다. 정리하려면 그 사실을 아는 사람이 별도 리비전으로
한다.

Revision ID: 39fa106ac455
Revises: 129eaa00e5ee
Create Date: 2026-08-24 15:24:28.405811
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "39fa106ac455"
down_revision: str | Sequence[str] | None = "129eaa00e5ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ingest_run",
        # 이미 있는 행에도 값이 필요하다. 옛 실행은 아무것도 안 솎았으므로 0 이 맞다.
        sa.Column("filtered", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ingest_run",
        # NULL 이면 안 솎았다는 뜻이다. 옛 실행이 전부 그렇다.
        sa.Column("filter_name", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ingest_run", "filter_name")
    op.drop_column("ingest_run", "filtered")
