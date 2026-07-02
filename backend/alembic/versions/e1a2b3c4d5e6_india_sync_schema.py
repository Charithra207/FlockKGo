"""india_sync_schema

Revision ID: e1a2b3c4d5e6
Revises: cd28fbd46a9f
Create Date: 2026-06-10 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = 'e1a2b3c4d5e6'
down_revision: Union[str, None] = '07593463a10a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- destinations: new columns ---
    op.add_column('destinations', sa.Column('osm_source_id', sa.String(100), nullable=True))
    op.create_index('ix_destinations_osm_source_id', 'destinations', ['osm_source_id'], unique=True)
    op.add_column('destinations', sa.Column('travel_dna', sa.JSON(), nullable=True))
    op.add_column('destinations', sa.Column('tourism_metadata', sa.JSON(), nullable=True))

    # --- sync_runs table ---
    op.create_table(
        'sync_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched', sa.Integer(), nullable=True),
        sa.Column('inserted', sa.Integer(), nullable=True),
        sa.Column('updated', sa.Integer(), nullable=True),
        sa.Column('deactivated', sa.Integer(), nullable=True),
        sa.Column('rejected', sa.Integer(), nullable=True),
        sa.Column('stage_counts', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- destination_availability table ---
    op.create_table(
        'destination_availability',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('destination_id', sa.Uuid(), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('reason', sa.String(200), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['destination_id'], ['destinations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dest_avail_destination_id', 'destination_availability', ['destination_id'], unique=False)


def downgrade() -> None:
    # --- destination_availability ---
    op.drop_index('ix_dest_avail_destination_id', table_name='destination_availability')
    op.drop_table('destination_availability')

    # --- sync_runs ---
    op.drop_table('sync_runs')

    # --- destinations: remove new columns ---
    op.drop_index('ix_destinations_osm_source_id', table_name='destinations')
    op.drop_column('destinations', 'tourism_metadata')
    op.drop_column('destinations', 'travel_dna')
    op.drop_column('destinations', 'osm_source_id')
