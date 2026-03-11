"""Add fuel_card_number to Driver

Revision ID: c1a2b3d4e5f6
Revises: 2bdcfd8fe03f
Create Date: 2026-03-12 01:23:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2bdcfd8fe03f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('drivers', sa.Column('fuel_card_number', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('drivers', 'fuel_card_number')
