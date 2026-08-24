"""베타_테스터_이름_비밀번호_게이트

Revision ID: c6f574b25198
Revises: 39fa106ac455
Create Date: 2026-08-24 17:17:53.847927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6f574b25198'
down_revision: Union[str, Sequence[str], None] = '39fa106ac455'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('company_account',
    sa.Column('company_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('password', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('company_id'),
    sa.UniqueConstraint('name')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('company_account')
