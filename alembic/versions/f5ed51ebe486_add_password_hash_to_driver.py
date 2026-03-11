"""Add password_hash to Driver

Revision ID: f5ed51ebe486
Revises: a9f3c1e2b4d6
Create Date: 2026-03-11 12:06:21.462062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5ed51ebe486'
down_revision: Union[str, Sequence[str], None] = 'a9f3c1e2b4d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('drivers', sa.Column('password_hash', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('drivers', 'password_hash')
