"""fleet_management_driver_iin_repairs

Revision ID: a9f3c1e2b4d6
Revises: ddc588eaa7ce
Create Date: 2026-03-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9f3c1e2b4d6'
down_revision: Union[str, Sequence[str], None] = 'ddc588eaa7ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make tg_id nullable (manually-created dispatcher drivers have no Telegram account yet)
    op.alter_column('drivers', 'tg_id', nullable=True)

    # Add IIN and passport scan to drivers
    op.add_column('drivers', sa.Column('iin', sa.String(12), nullable=True))
    op.add_column('drivers', sa.Column('passport_r2_url', sa.String(), nullable=True))

    # Add year to vehicles
    op.add_column('vehicles', sa.Column('year', sa.Integer(), nullable=True))

    # Create vehicle_repairs table
    op.create_table(
        'vehicle_repairs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('vehicle_id', sa.Integer(), sa.ForeignKey('vehicles.id'), nullable=False),
        sa.Column('trip_id', sa.Integer(), sa.ForeignKey('trips.id'), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='OPEN'),
        sa.Column('priority', sa.String(), nullable=False, server_default='NORMAL'),
        sa.Column('reported_by', sa.String(), nullable=True),
        sa.Column('resolved_by', sa.String(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('vehicle_repairs')
    op.drop_column('vehicles', 'year')
    op.drop_column('drivers', 'passport_r2_url')
    op.drop_column('drivers', 'iin')
    op.alter_column('drivers', 'tg_id', nullable=False)
