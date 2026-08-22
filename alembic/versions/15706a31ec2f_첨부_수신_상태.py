"""첨부 수신 상태

Revision ID: 15706a31ec2f
Revises: a1e0c7d4f2b9
Create Date: 2026-08-17 02:00:16.304678

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15706a31ec2f"
down_revision: str | None = "a1e0c7d4f2b9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 기본값이 '미수신'이고 **그게 정상 상태다**(plan/07). 전량을 미리 받지 않는다.
    # 기존 3,354행이 전부 이 값으로 채워지고, 그래서 분모는 첫날부터 정확하다.
    op.add_column(
        "attachment",
        sa.Column("fetch_status", sa.String(16), nullable=False, server_default="미수신"),
    )
    op.add_column("attachment", sa.Column("fetched_at", sa.DateTime(timezone=True)))
    # 저장소 루트 기준 상대경로. 절대경로를 넣으면 캐시를 옮길 때 전부 깨진다.
    op.add_column("attachment", sa.Column("local_path", sa.Text()))
    op.add_column("attachment", sa.Column("byte_size", sa.Integer()))
    op.add_column("attachment", sa.Column("content_sha256", sa.String(64)))
    # 받은 첫 바이트가 확장자와 어긋났나. **실패가 아니라 경고다.**
    # 첨부 URL 도 실패를 HTTP 200 으로 준다. 오류 HTML 이 .hwp 이름으로 온다.
    op.add_column(
        "attachment",
        sa.Column("sniff_mismatch", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("attachment", sa.Column("fetch_error", sa.Text()))

    op.create_index("ix_attachment_content_sha256", "attachment", ["content_sha256"])
    op.create_index("ix_attachment_fetch_status", "attachment", ["fetch_status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_attachment_fetch_status", table_name="attachment")
    op.drop_index("ix_attachment_content_sha256", table_name="attachment")
    for col in (
        "fetch_error",
        "sniff_mismatch",
        "content_sha256",
        "byte_size",
        "local_path",
        "fetched_at",
        "fetch_status",
    ):
        op.drop_column("attachment", col)
