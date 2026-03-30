"""add panel users

Revision ID: a3f9e1c2d4b8
Revises: df50fbcf909c
Create Date: 2026-03-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f9e1c2d4b8'
down_revision: Union[str, Sequence[str], None] = 'df50fbcf909c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'panel_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(32), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_panel_users_id'), 'panel_users', ['id'], unique=False)
    op.create_index(op.f('ix_panel_users_username'), 'panel_users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_panel_users_username'), table_name='panel_users')
    op.drop_index(op.f('ix_panel_users_id'), table_name='panel_users')
    op.drop_table('panel_users')
