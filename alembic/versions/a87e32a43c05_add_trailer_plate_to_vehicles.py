"""add_trailer_plate_to_vehicles

Revision ID: a87e32a43c05
Revises: a3f9e1c2d4b8
Create Date: 2026-04-03 10:34:57.558398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a87e32a43c05'
down_revision: Union[str, Sequence[str], None] = 'a3f9e1c2d4b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vehicles', sa.Column('trailer_plate', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicles', 'trailer_plate')
