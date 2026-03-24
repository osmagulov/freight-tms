"""add_predictive_maintenance

Revision ID: 54d9deefe0e4
Revises: e1234567890a
Create Date: 2026-03-24 12:02:05.033262

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '54d9deefe0e4'
down_revision: Union[str, Sequence[str], None] = 'e1234567890a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vehicles', sa.Column('maintenance_interval_km', sa.Integer(), nullable=True, server_default='60000'))
    op.add_column('vehicles', sa.Column('last_maintenance_odometer', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('vehicles', 'last_maintenance_odometer')
    op.drop_column('vehicles', 'maintenance_interval_km')
