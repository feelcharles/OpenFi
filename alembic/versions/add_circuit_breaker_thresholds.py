"""Add circuit breaker thresholds to EA profiles

Revision ID: add_cb_thresholds
Revises: add_core_business
Create Date: 2026-03-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_cb_thresholds'
down_revision: Union[str, None] = 'add_core_business'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Add circuit breaker threshold columns to ea_profiles table."""
    
    # Add circuit breaker threshold columns
    op.add_column('ea_profiles', sa.Column('max_consecutive_losses', sa.Integer(), nullable=True, server_default='3'))
    op.add_column('ea_profiles', sa.Column('max_consecutive_failures', sa.Integer(), nullable=True, server_default='5'))
    op.add_column('ea_profiles', sa.Column('loss_time_window_seconds', sa.Integer(), nullable=True, server_default='300'))

def downgrade() -> None:
    """Remove circuit breaker threshold columns from ea_profiles table."""
    
    op.drop_column('ea_profiles', 'loss_time_window_seconds')
    op.drop_column('ea_profiles', 'max_consecutive_failures')
    op.drop_column('ea_profiles', 'max_consecutive_losses')
