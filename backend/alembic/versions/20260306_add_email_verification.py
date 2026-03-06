"""add email verification support

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_email_verified to users (default True so existing users unaffected)
    op.add_column(
        'users',
        sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default='true'),
    )

    # Create verification_codes table
    op.create_table(
        'verification_codes',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('purpose', sa.String(length=30), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('expires_at', sa.BigInteger(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_verification_codes_user_id', 'verification_codes', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_verification_codes_user_id', table_name='verification_codes')
    op.drop_table('verification_codes')
    op.drop_column('users', 'is_email_verified')
