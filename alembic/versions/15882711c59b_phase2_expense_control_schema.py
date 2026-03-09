"""phase2_expense_control_schema

Revision ID: 15882711c59b
Revises: a1b2c3d4e5f6
Create Date: 2026-03-09 08:48:20.297277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '15882711c59b'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to expenses table
    op.add_column('expenses', sa.Column('status', sa.String(), nullable=False, server_default='PENDING'))
    op.add_column('expenses', sa.Column('approved_by', sa.String(), nullable=True))
    op.add_column('expenses', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('expenses', sa.Column('rejection_comment', sa.String(), nullable=True))
    op.add_column('expenses', sa.Column('liters', sa.Float(), nullable=True))
    op.add_column('expenses', sa.Column('odometer_reading', sa.Integer(), nullable=True))
    op.add_column('expenses', sa.Column('station', sa.String(), nullable=True))
    op.add_column('expenses', sa.Column('fx_rate', sa.Float(), nullable=True))
    op.add_column('expenses', sa.Column('amount_kzt', sa.Float(), nullable=True))
    op.add_column('expenses', sa.Column('idempotency_minute', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        'uq_expense_idempotent',
        'expenses',
        ['trip_id', 'expense_type', 'amount', 'idempotency_minute']
    )

    # Create fuel_anomalies table
    op.create_table(
        'fuel_anomalies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('expense_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('actual_per_100km', sa.Float(), nullable=False),
        sa.Column('norm_per_100km', sa.Float(), nullable=False),
        sa.Column('threshold_per_100km', sa.Float(), nullable=False),
        sa.Column('excess_percent', sa.Float(), nullable=False),
        sa.Column('is_false_alarm', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['expense_id'], ['expenses.id']),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_fuel_anomalies_id'), 'fuel_anomalies', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fuel_anomalies_id'), table_name='fuel_anomalies')
    op.drop_table('fuel_anomalies')
    op.drop_constraint('uq_expense_idempotent', 'expenses', type_='unique')
    op.drop_column('expenses', 'idempotency_minute')
    op.drop_column('expenses', 'amount_kzt')
    op.drop_column('expenses', 'fx_rate')
    op.drop_column('expenses', 'station')
    op.drop_column('expenses', 'odometer_reading')
    op.drop_column('expenses', 'liters')
    op.drop_column('expenses', 'rejection_comment')
    op.drop_column('expenses', 'approved_at')
    op.drop_column('expenses', 'approved_by')
    op.drop_column('expenses', 'status')
