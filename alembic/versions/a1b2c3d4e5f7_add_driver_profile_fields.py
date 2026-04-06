"""Add driver profile fields: photo, license, passport numbers

Revision ID: a1b2c3d4e5f7
Revises: f248495c4351
Create Date: 2026-04-07 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'f248495c4351'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('drivers', sa.Column('profile_photo_url', sa.String(), nullable=True))
    op.add_column('drivers', sa.Column('license_number', sa.String(32), nullable=True))
    op.add_column('drivers', sa.Column('license_expiry', sa.Date(), nullable=True))
    op.add_column('drivers', sa.Column('passport_number', sa.String(32), nullable=True))
    op.add_column('drivers', sa.Column('passport_expiry', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('drivers', 'passport_expiry')
    op.drop_column('drivers', 'passport_number')
    op.drop_column('drivers', 'license_expiry')
    op.drop_column('drivers', 'license_number')
    op.drop_column('drivers', 'profile_photo_url')
