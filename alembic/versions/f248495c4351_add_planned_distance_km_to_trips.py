"""add_planned_distance_km_to_trips

Revision ID: f248495c4351
Revises: a87e32a43c05
Create Date: 2026-04-03 10:48:34.585248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f248495c4351'
down_revision: Union[str, Sequence[str], None] = 'a87e32a43c05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trips', sa.Column('planned_distance_km', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('trips', 'planned_distance_km')
