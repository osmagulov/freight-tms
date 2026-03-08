"""phase1_add_photo_r2_url

Revision ID: a1b2c3d4e5f6
Revises: 4d9175cac075
Create Date: 2026-03-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4d9175cac075'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add photo_r2_url column to expenses table for durable Cloudflare R2 storage."""
    op.add_column('expenses',
        sa.Column('photo_r2_url', sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Remove photo_r2_url column from expenses table."""
    op.drop_column('expenses', 'photo_r2_url')
