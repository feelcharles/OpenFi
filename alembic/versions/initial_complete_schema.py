"""Initial complete schema

Revision ID: initial_complete
Revises: 
Create Date: 2026-03-05 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'initial_complete'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Create all database tables with complete schema."""
    
    # ============================================
    # Create users table with all fields
    # ============================================
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('username', sa.String(50), nullable=False, unique=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='trader'),
        # Timezone and display settings
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Shanghai'),
        sa.Column('datetime_format', sa.String(50), nullable=True, server_default='%Y-%m-%d %H:%M:%S'),
        sa.Column('show_timezone_name', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('use_12_hour_format', sa.Boolean(), nullable=True, server_default='false'),
        # Multi-user support
        sa.Column('parent_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_parent_user_id', 'users', ['parent_user_id'])
    op.create_foreign_key('fk_users_parent_user_id', 'users', 'users', ['parent_user_id'], ['id'])
    
    # ============================================
    # Create brokers table
    # ============================================
    op.create_table(
        'brokers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('broker_name', sa.String(100), nullable=False),
        sa.Column('broker_type', sa.String(50), nullable=False),
        sa.Column('connection_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('credentials', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('capabilities', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_brokers_broker_name', 'brokers', ['broker_name'])
    op.create_index('ix_brokers_broker_type', 'brokers', ['broker_type'])
    op.create_index('ix_brokers_enabled', 'brokers', ['enabled'])
    
    # ============================================
    # Create trading_accounts table
    # ============================================
    op.create_table(
        'trading_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('broker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_number', sa.String(100), nullable=False),
        sa.Column('account_name', sa.String(100), nullable=False),
        sa.Column('account_type', sa.String(20), nullable=False, server_default='demo'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('trading_limits', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('balance', sa.Numeric(precision=20, scale=2), server_default='0.0'),
        sa.Column('equity', sa.Numeric(precision=20, scale=2), server_default='0.0'),
        sa.Column('margin_used', sa.Numeric(precision=20, scale=2), server_default='0.0'),
        sa.Column('margin_free', sa.Numeric(precision=20, scale=2), server_default='0.0'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_trading_accounts_user_id', 'trading_accounts', ['user_id'])
    op.create_index('ix_trading_accounts_broker_id', 'trading_accounts', ['broker_id'])
    op.create_index('ix_trading_accounts_account_number', 'trading_accounts', ['account_number'])
    op.create_index('ix_trading_accounts_is_active', 'trading_accounts', ['is_active'])
    
    # ============================================
    # Create user_broker_permissions table
    # ============================================
    op.create_table(
        'user_broker_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('broker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission_level', sa.String(20), nullable=False, server_default='read_only'),
        sa.Column('specific_permissions', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('granted_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id']),
    )
    op.create_index('ix_user_broker_permissions_user_id', 'user_broker_permissions', ['user_id'])
    op.create_index('ix_user_broker_permissions_broker_id', 'user_broker_permissions', ['broker_id'])
    op.create_index('ix_user_broker_permissions_is_active', 'user_broker_permissions', ['is_active'])
    
    # ============================================
    # Create ea_profiles table
    # ============================================
    op.create_table(
        'ea_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ea_name', sa.String(100), nullable=False),
        sa.Column('symbols', postgresql.ARRAY(sa.String), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('risk_per_trade', sa.Numeric(5, 4), nullable=False),
        sa.Column('max_positions', sa.Integer, nullable=False, server_default='1'),
        sa.Column('max_total_risk', sa.Numeric(5, 4), nullable=False),
        sa.Column('strategy_logic_description', sa.Text),
        sa.Column('auto_execution', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ea_profiles_user_id', 'ea_profiles', ['user_id'])
    op.create_index('ix_ea_profiles_ea_name', 'ea_profiles', ['ea_name'])
    op.create_unique_constraint('uq_ea_profiles_user_ea', 'ea_profiles', ['user_id', 'ea_name'])
    
    # ============================================
    # Create push_configs table
    # ============================================
    op.create_table(
        'push_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('credentials', postgresql.JSONB, nullable=False),
        sa.Column('template', sa.Text),
        sa.Column('alert_rules', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_push_configs_user_id', 'push_configs', ['user_id'])
    op.create_unique_constraint('uq_push_configs_user_channel', 'push_configs', ['user_id', 'channel'])
    
    # ============================================
    # Create trades table
    # ============================================
    op.create_table(
        'trades',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('ea_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ea_profiles.id'), nullable=False),
        sa.Column('broker_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('trading_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('signal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('volume', sa.Numeric(10, 2), nullable=False),
        sa.Column('entry_price', sa.Numeric(20, 5), nullable=False),
        sa.Column('stop_loss', sa.Numeric(20, 5)),
        sa.Column('take_profit', sa.Numeric(20, 5)),
        sa.Column('execution_price', sa.Numeric(20, 5)),
        sa.Column('broker_order_id', sa.String(100)),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True)),
        sa.Column('closed_at', sa.DateTime(timezone=True)),
        sa.Column('pnl', sa.Numeric(20, 2)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id']),
        sa.ForeignKeyConstraint(['trading_account_id'], ['trading_accounts.id']),
    )
    op.create_index('ix_trades_user_id', 'trades', ['user_id'])
    op.create_index('ix_trades_ea_profile_id', 'trades', ['ea_profile_id'])
    op.create_index('ix_trades_broker_id', 'trades', ['broker_id'])
    op.create_index('ix_trades_trading_account_id', 'trades', ['trading_account_id'])
    op.create_index('ix_trades_signal_id', 'trades', ['signal_id'])
    op.create_index('ix_trades_symbol', 'trades', ['symbol'])
    op.create_index('ix_trades_status', 'trades', ['status'])
    op.create_index('ix_trades_executed_at', 'trades', ['executed_at'])
    op.create_index('ix_trades_created_at', 'trades', ['created_at'])
    
    # ============================================
    # Create fetch_sources table
    # ============================================
    op.create_table(
        'fetch_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source_id', sa.String(50), nullable=False, unique=True),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('api_endpoint', sa.Text, nullable=False),
        sa.Column('credentials', postgresql.JSONB),
        sa.Column('schedule_type', sa.String(20), nullable=False),
        sa.Column('schedule_config', postgresql.JSONB, nullable=False),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_fetch_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_fetch_sources_source_id', 'fetch_sources', ['source_id'])
    op.create_index('ix_fetch_sources_source_type', 'fetch_sources', ['source_type'])
    op.create_index('ix_fetch_sources_enabled', 'fetch_sources', ['enabled'])
    
    # ============================================
    # Create llm_logs table
    # ============================================
    op.create_table(
        'llm_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('prompt_tokens', sa.Integer),
        sa.Column('completion_tokens', sa.Integer),
        sa.Column('total_tokens', sa.Integer),
        sa.Column('latency_ms', sa.Integer),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_llm_logs_provider', 'llm_logs', ['provider'])
    op.create_index('ix_llm_logs_model', 'llm_logs', ['model'])
    op.create_index('ix_llm_logs_status', 'llm_logs', ['status'])
    op.create_index('ix_llm_logs_created_at', 'llm_logs', ['created_at'])

def downgrade() -> None:
    """Drop all tables in reverse order to respect foreign key constraints."""
    op.drop_table('llm_logs')
    op.drop_table('fetch_sources')
    op.drop_table('trades')
    op.drop_table('push_configs')
    op.drop_table('ea_profiles')
    op.drop_table('user_broker_permissions')
    op.drop_table('trading_accounts')
    op.drop_table('brokers')
    op.drop_table('users')
