"""add coin_metadata table

Revision ID: a1b2c3d4e5f6
Revises: f98787a84045
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f98787a84045'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'coin_metadata',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('coingecko_id', sa.String(length=100), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('market_cap_rank', sa.BigInteger(), nullable=True),
        sa.Column('market_cap', sa.Numeric(precision=30, scale=2), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('ath', sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column('ath_date_ms', sa.BigInteger(), nullable=True),
        sa.Column('atl', sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column('atl_date_ms', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_coin_metadata_symbol', 'coin_metadata', ['symbol'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_coin_metadata_symbol', table_name='coin_metadata')
    op.drop_table('coin_metadata')
