"""add_document_tables

Revision ID: 2bdcfd8fe03f
Revises: f5ed51ebe486
Create Date: 2026-03-11 12:20:00.886526

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2bdcfd8fe03f'
down_revision: Union[str, Sequence[str], None] = 'f5ed51ebe486'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "driver_documents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("driver_id", sa.Integer(), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("r2_url", sa.String(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "vehicle_documents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("r2_url", sa.String(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("vehicle_documents")
    op.drop_table("driver_documents")
