"""add is_demo column to accounts table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'accounts',
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default='false',
                   comment='Whether this is a demo account with fake data'),
    )


def downgrade() -> None:
    op.drop_column('accounts', 'is_demo')
