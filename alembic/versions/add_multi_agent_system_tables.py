"""Add multi-agent system tables

Revision ID: add_multi_agent_system
Revises: add_factor_system
Create Date: 2026-03-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_multi_agent_system'
down_revision: Union[str, None] = 'add_factor_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Create multi-agent system tables."""
    
    # ============================================
    # Create agents table
    # ============================================
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text()),
        sa.Column('status', sa.String(50), nullable=False, server_default='inactive'),
        sa.Column('priority', sa.String(50), nullable=False, server_default='normal'),
        sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String()), server_default='{}'),
        sa.Column('category', sa.String(100)),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint("status IN ('active', 'inactive', 'paused', 'error')", name='ck_agents_status'),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'critical')", name='ck_agents_priority'),
    )
    op.create_index('ix_agents_name', 'agents', ['name'])
    op.create_index('ix_agents_status', 'agents', ['status'])
    op.create_index('ix_agents_owner_user_id', 'agents', ['owner_user_id'])
    op.create_index('ix_agents_category', 'agents', ['category'])
    op.create_index('ix_agents_tags', 'agents', ['tags'], postgresql_using='gin')
    
    # ============================================
    # Create agent_configs table
    # ============================================
    op.create_table(
        'agent_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('change_description', sa.Text()),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('agent_id', 'version', name='uq_agent_configs_agent_version'),
    )
    op.create_index('ix_agent_configs_agent_id', 'agent_configs', ['agent_id'])
    op.create_index('ix_agent_configs_agent_version', 'agent_configs', ['agent_id', 'version'])
    
    # ============================================
    # Create agent_assets table
    # ============================================
    op.create_table(
        'agent_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('weight', sa.Numeric(5, 4), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('agent_id', 'symbol', name='uq_agent_assets_agent_symbol'),
        sa.CheckConstraint('weight >= 0 AND weight <= 1', name='ck_agent_assets_weight'),
        sa.CheckConstraint("category IN ('forex', 'crypto', 'commodities', 'indices', 'stocks')", name='ck_agent_assets_category'),
    )
    op.create_index('ix_agent_assets_agent_id', 'agent_assets', ['agent_id'])
    op.create_index('ix_agent_assets_symbol', 'agent_assets', ['symbol'])
    op.create_index('ix_agent_assets_category', 'agent_assets', ['category'])
    
    # ============================================
    # Create agent_triggers table
    # ============================================
    op.create_table(
        'agent_triggers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('trigger_config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.CheckConstraint("trigger_type IN ('keywords', 'factors', 'price', 'price_change', 'time', 'manual')", name='ck_agent_triggers_type'),
    )
    op.create_index('ix_agent_triggers_agent_id', 'agent_triggers', ['agent_id'])
    op.create_index('ix_agent_triggers_type', 'agent_triggers', ['trigger_type'])
    op.create_index('ix_agent_triggers_enabled', 'agent_triggers', ['agent_id', 'enabled'])
    
    # ============================================
    # Create agent_push_configs table
    # ============================================
    op.create_table(
        'agent_push_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('push_config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_agent_push_configs_agent_id', 'agent_push_configs', ['agent_id'])
    
    # ============================================
    # Create agent_bot_connections table
    # ============================================
    op.create_table(
        'agent_bot_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bot_type', sa.String(50), nullable=False),
        sa.Column('credentials_encrypted', sa.Text(), nullable=False),
        sa.Column('target_channel', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='inactive'),
        sa.Column('health_check_interval', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('last_health_check', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.CheckConstraint("bot_type IN ('telegram', 'discord', 'slack', 'webhook')", name='ck_agent_bot_connections_type'),
        sa.CheckConstraint("status IN ('active', 'inactive', 'error')", name='ck_agent_bot_connections_status'),
    )
    op.create_index('ix_agent_bot_connections_agent_id', 'agent_bot_connections', ['agent_id'])
    op.create_index('ix_agent_bot_connections_bot_type', 'agent_bot_connections', ['bot_type'])
    op.create_index('ix_agent_bot_connections_status', 'agent_bot_connections', ['status'])
    
    # ============================================
    # Create agent_metrics table
    # ============================================
    op.create_table(
        'agent_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_type', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Numeric(20, 4), nullable=False),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_agent_metrics_agent_id_timestamp', 'agent_metrics', ['agent_id', 'timestamp'])
    op.create_index('ix_agent_metrics_metric_type', 'agent_metrics', ['metric_type'])
    op.create_index('ix_agent_metrics_timestamp', 'agent_metrics', ['timestamp'])
    
    # ============================================
    # Create agent_logs table
    # ============================================
    op.create_table(
        'agent_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('log_level', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.CheckConstraint("log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name='ck_agent_logs_level'),
    )
    op.create_index('ix_agent_logs_agent_id_timestamp', 'agent_logs', ['agent_id', 'timestamp'])
    op.create_index('ix_agent_logs_log_level', 'agent_logs', ['log_level'])
    op.create_index('ix_agent_logs_timestamp', 'agent_logs', ['timestamp'])

def downgrade() -> None:
    """Drop multi-agent system tables."""
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('agent_logs')
    op.drop_table('agent_metrics')
    op.drop_table('agent_bot_connections')
    op.drop_table('agent_push_configs')
    op.drop_table('agent_triggers')
    op.drop_table('agent_assets')
    op.drop_table('agent_configs')
    op.drop_table('agents')
