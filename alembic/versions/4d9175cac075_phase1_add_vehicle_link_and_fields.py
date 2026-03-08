"""phase1_add_vehicle_link_and_fields

Revision ID: 4d9175cac075
Revises: 18ed19dece10
Create Date: 2026-03-09 03:37:56.066317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d9175cac075'
down_revision: Union[str, Sequence[str], None] = '18ed19dece10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add vehicle_id FK to drivers table
    op.add_column('drivers',
        sa.Column('vehicle_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_drivers_vehicle_id', 'drivers', 'vehicles',
        ['vehicle_id'], ['id']
    )
    # Add vehicle detail fields
    op.add_column('vehicles', sa.Column('make', sa.String(), nullable=True))
    op.add_column('vehicles', sa.Column('model', sa.String(), nullable=True))
    op.add_column('vehicles',
        sa.Column('fuel_norm_per_100km', sa.Float(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_drivers_vehicle_id', 'drivers', type_='foreignkey')
    op.drop_column('drivers', 'vehicle_id')
    op.drop_column('vehicles', 'fuel_norm_per_100km')
    op.drop_column('vehicles', 'model')
    op.drop_column('vehicles', 'make')
