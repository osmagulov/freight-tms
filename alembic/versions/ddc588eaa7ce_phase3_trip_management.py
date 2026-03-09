"""phase3_trip_management

Revision ID: ddc588eaa7ce
Revises: 15882711c59b
Create Date: 2026-03-09 13:24:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddc588eaa7ce'
down_revision: Union[str, Sequence[str], None] = '15882711c59b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Phase 3 columns to trips table (TRIP-01)
    op.add_column('trips', sa.Column('client_name', sa.String(), nullable=True))
    op.add_column('trips', sa.Column('planned_departure', sa.DateTime(timezone=True), nullable=True))
    op.add_column('trips', sa.Column('planned_arrival', sa.DateTime(timezone=True), nullable=True))
    op.add_column('trips', sa.Column('delivery_status', sa.String(), nullable=True))

    # Create trip_documents table (TRIP-04, TRIP-05)
    op.create_table(
        'trip_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('r2_url', sa.String(), nullable=True),
        sa.Column('tg_file_id', sa.String(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_trip_documents_id'), 'trip_documents', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trip_documents_id'), table_name='trip_documents')
    op.drop_table('trip_documents')
    op.drop_column('trips', 'delivery_status')
    op.drop_column('trips', 'planned_arrival')
    op.drop_column('trips', 'planned_departure')
    op.drop_column('trips', 'client_name')
