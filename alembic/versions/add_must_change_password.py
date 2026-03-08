"""add must_change_password to users

Revision ID: add_must_change_password
Revises: initial_complete_schema
Create Date: 2024-03-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_must_change_password'
down_revision = 'initial_complete_schema'
branch_labels = None
depends_on = None

def upgrade():
    # Add must_change_password column to users table
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='false'))

def downgrade():
    # Remove must_change_password column from users table
    op.drop_column('users', 'must_change_password')
