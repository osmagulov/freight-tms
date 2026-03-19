"""add trip price analytics

Revision ID: e1234567890a
Revises: f5ed51ebe486
Create Date: 2026-03-19 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1234567890a'
down_revision: Union[str, Sequence[str], None] = 'f5ed51ebe486'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trips', sa.Column('price', sa.Float(), nullable=True))
    op.add_column('trips', sa.Column('price_currency', sa.String(length=3), server_default='KZT', nullable=True))


def downgrade() -> None:
    op.drop_column('trips', 'price_currency')
    op.drop_column('trips', 'price')
