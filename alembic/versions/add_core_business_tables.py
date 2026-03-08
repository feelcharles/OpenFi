"""Add core business module tables

Revision ID: add_core_business
Revises: initial_complete
Create Date: 2026-03-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_core_business'
down_revision: Union[str, None] = 'initial_complete'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Create core business module tables and add optimistic locking."""
    
    # ============================================
    # Add optimistic locking (version column) to existing tables
    # ============================================
    op.add_column('trades', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('ea_profiles', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    
    # ============================================
    # Create signals table
    # ============================================
    op.create_table(
        'signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('data_type', sa.String(50), nullable=False),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('relevance_score', sa.Integer(), nullable=False),
        sa.Column('potential_impact', sa.String(20), nullable=False, server_default='low'),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('suggested_actions', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('related_symbols', postgresql.ARRAY(sa.String(20))),
        sa.Column('confidence', sa.Numeric(5, 4)),
        sa.Column('reasoning', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('relevance_score >= 0 AND relevance_score <= 100', name='ck_signals_relevance_score'),
        sa.CheckConstraint("potential_impact IN ('low', 'medium', 'high')", name='ck_signals_potential_impact'),
    )
    op.create_index('ix_signals_created_at', 'signals', ['created_at'])
    op.create_index('ix_signals_relevance_score', 'signals', ['relevance_score'])
    op.create_index('ix_signals_source_type', 'signals', ['source_type'])
    
    # ============================================
    # Create notifications table
    # ============================================
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('signal_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text()),
        sa.Column('sent_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['signal_id'], ['signals.id']),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name='ck_notifications_status'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_status', 'notifications', ['status'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
    
    # ============================================
    # Create alert_rules table
    # ============================================
    op.create_table(
        'alert_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_name', sa.String(100), nullable=False),
        sa.Column('min_relevance_score', sa.Integer()),
        sa.Column('required_symbols', postgresql.ARRAY(sa.String(20))),
        sa.Column('required_impact_levels', postgresql.ARRAY(sa.String(20))),
        sa.Column('time_windows', postgresql.ARRAY(sa.String(50))),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint('min_relevance_score IS NULL OR (min_relevance_score >= 0 AND min_relevance_score <= 100)', name='ck_alert_rules_min_relevance_score'),
    )
    op.create_index('ix_alert_rules_user_id', 'alert_rules', ['user_id'])
    op.create_index('ix_alert_rules_enabled', 'alert_rules', ['enabled'])
    
    # ============================================
    # Create circuit_breaker_states table
    # ============================================
    op.create_table(
        'circuit_breaker_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('ea_profile_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('consecutive_losses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('triggered_at', sa.DateTime(timezone=True)),
        sa.Column('trigger_reason', sa.Text()),
        sa.Column('reset_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['ea_profile_id'], ['ea_profiles.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_circuit_breaker_states_ea_profile_id', 'circuit_breaker_states', ['ea_profile_id'])
    op.create_index('ix_circuit_breaker_states_is_active', 'circuit_breaker_states', ['is_active'])
    
    # ============================================
    # Create audit_logs table
    # ============================================
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True)),
        sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('ip_address', sa.String(45)),  # IPv6 compatible
        sa.Column('user_agent', sa.Text()),
        sa.Column('signature', sa.String(255)),  # HMAC-SHA256 signature
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

def downgrade() -> None:
    """Drop core business module tables and remove optimistic locking."""
    
    # Drop tables in reverse order
    op.drop_table('audit_logs')
    op.drop_table('circuit_breaker_states')
    op.drop_table('alert_rules')
    op.drop_table('notifications')
    op.drop_table('signals')
    
    # Remove optimistic locking columns
    op.drop_column('ea_profiles', 'version')
    op.drop_column('trades', 'version')
