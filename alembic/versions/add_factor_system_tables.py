"""Add factor system tables

Revision ID: add_factor_system
Revises: add_cb_thresholds
Create Date: 2026-03-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_factor_system'
down_revision: Union[str, None] = 'add_cb_thresholds'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Create factor system tables."""
    
    # ============================================
    # Create factors table
    # ============================================
    op.create_table(
        'factors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('factor_name', sa.String(100), nullable=False, unique=True),
        sa.Column('factor_code', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('category', sa.String(50)),
        sa.Column('data_dependencies', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.CheckConstraint("category IN ('technical', 'fundamental', 'sentiment', 'alternative') OR category IS NULL", name='ck_factors_category'),
    )
    op.create_index('ix_factors_factor_name', 'factors', ['factor_name'])
    op.create_index('ix_factors_category', 'factors', ['category'])
    op.create_index('ix_factors_is_active', 'factors', ['is_active'])
    
    # ============================================
    # Create factor_values table
    # ============================================
    op.create_table(
        'factor_values',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('factor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('value', sa.Numeric(20, 8)),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['factor_id'], ['factors.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_factor_values_factor_id', 'factor_values', ['factor_id'])
    op.create_index('ix_factor_values_symbol', 'factor_values', ['symbol'])
    op.create_index('ix_factor_values_date', 'factor_values', ['date'])
    # Composite index for efficient queries
    op.create_index('ix_factor_values_factor_symbol_date', 'factor_values', ['factor_id', 'symbol', 'date'])
    
    # ============================================
    # Create backtest_results table
    # ============================================
    op.create_table(
        'backtest_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('strategy_name', sa.String(100), nullable=False),
        sa.Column('strategy_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('initial_capital', sa.Numeric(20, 2), nullable=False),
        sa.Column('final_capital', sa.Numeric(20, 2)),
        sa.Column('total_return', sa.Numeric(10, 4)),
        sa.Column('annual_return', sa.Numeric(10, 4)),
        sa.Column('max_drawdown', sa.Numeric(10, 4)),
        sa.Column('sharpe_ratio', sa.Numeric(10, 4)),
        sa.Column('win_rate', sa.Numeric(5, 4)),
        sa.Column('profit_loss_ratio', sa.Numeric(10, 4)),
        sa.Column('total_trades', sa.Integer()),
        sa.Column('equity_curve', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('trade_details', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint('initial_capital > 0', name='ck_backtest_results_initial_capital'),
        sa.CheckConstraint('start_date <= end_date', name='ck_backtest_results_date_range'),
    )
    op.create_index('ix_backtest_results_user_id', 'backtest_results', ['user_id'])
    op.create_index('ix_backtest_results_created_at', 'backtest_results', ['created_at'])
    
    # ============================================
    # Create factor_combinations table
    # ============================================
    op.create_table(
        'factor_combinations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('combination_name', sa.String(100), nullable=False),
        sa.Column('factor_weights', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('optimization_method', sa.String(50)),
        sa.Column('description', sa.Text()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint("optimization_method IN ('equal_weight', 'ic_weighted', 'max_sharpe') OR optimization_method IS NULL", name='ck_factor_combinations_optimization_method'),
    )
    op.create_index('ix_factor_combinations_user_id', 'factor_combinations', ['user_id'])
    op.create_index('ix_factor_combinations_is_active', 'factor_combinations', ['is_active'])
    
    # ============================================
    # Create screening_presets table
    # ============================================
    op.create_table(
        'screening_presets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('preset_name', sa.String(100), nullable=False),
        sa.Column('factor_conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('additional_filters', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_screening_presets_user_id', 'screening_presets', ['user_id'])
    
    # ============================================
    # Create factor_analysis_logs table
    # ============================================
    op.create_table(
        'factor_analysis_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('factor_id', postgresql.UUID(as_uuid=True)),
        sa.Column('backtest_id', postgresql.UUID(as_uuid=True)),
        sa.Column('analysis_type', sa.String(50), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('response', sa.Text(), nullable=False),
        sa.Column('llm_provider', sa.String(50)),
        sa.Column('llm_model', sa.String(100)),
        sa.Column('tokens_used', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['factor_id'], ['factors.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['backtest_id'], ['backtest_results.id'], ondelete='SET NULL'),
        sa.CheckConstraint("analysis_type IN ('performance', 'combination', 'query')", name='ck_factor_analysis_logs_analysis_type'),
    )
    op.create_index('ix_factor_analysis_logs_factor_id', 'factor_analysis_logs', ['factor_id'])
    op.create_index('ix_factor_analysis_logs_backtest_id', 'factor_analysis_logs', ['backtest_id'])
    op.create_index('ix_factor_analysis_logs_created_at', 'factor_analysis_logs', ['created_at'])

def downgrade() -> None:
    """Drop factor system tables."""
    
    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_table('factor_analysis_logs')
    op.drop_table('screening_presets')
    op.drop_table('factor_combinations')
    op.drop_table('backtest_results')
    op.drop_table('factor_values')
    op.drop_table('factors')
