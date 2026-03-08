# Database Migrations

This directory contains Alembic database migrations for HyperBrain Lite.

## Prerequisites

Ensure you have the following environment variables set:

```bash
DB_USER=hyperbrain
DB_PASSWORD=hyperbrain_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=system_core
```

You can set these in a `.env` file in the project root.

## Running Migrations

### Apply all pending migrations

```bash
python -m alembic upgrade head
```

### Rollback one migration

```bash
python -m alembic downgrade -1
```

### Rollback all migrations

```bash
python -m alembic downgrade base
```

### View migration history

```bash
python -m alembic history
```

### View current migration version

```bash
python -m alembic current
```

## Creating New Migrations

### Auto-generate migration from model changes

```bash
python -m alembic revision --autogenerate -m "description of changes"
```

### Create empty migration

```bash
python -m alembic revision -m "description of changes"
```

## Database Schema

The initial migration creates the following tables:

### users
- User accounts with authentication and role information
- Columns: id (UUID), username, email, password_hash, role, created_at, updated_at
- Indexes: username, email

### ea_profiles
- Expert Advisor (EA) trading strategy configurations
- Columns: id (UUID), user_id (FK), ea_name, symbols (array), timeframe, risk_per_trade, max_total_risk, strategy_logic_description, auto_execution, created_at, updated_at
- Indexes: user_id, ea_name
- Unique constraint: (user_id, ea_name)
- Foreign key: user_id → users.id (CASCADE DELETE)

### push_configs
- Multi-channel push notification configurations
- Columns: id (UUID), user_id (FK), channel, enabled, credentials (JSONB), template, alert_rules (JSONB), created_at
- Indexes: user_id
- Unique constraint: (user_id, channel)
- Foreign key: user_id → users.id (CASCADE DELETE)

### trades
- Trade execution records
- Columns: id (UUID), user_id (FK), ea_profile_id (FK), signal_id, symbol, direction, volume, entry_price, stop_loss, take_profit, execution_price, broker_order_id, status, executed_at, closed_at, pnl, created_at
- Indexes: user_id, ea_profile_id, signal_id, symbol, status, executed_at, created_at
- Foreign keys: user_id → users.id, ea_profile_id → ea_profiles.id

### fetch_sources
- Data source configurations for the fetch engine
- Columns: id (UUID), source_id, source_type, api_endpoint, credentials (JSONB), schedule_type, schedule_config (JSONB), enabled, last_fetch_at, created_at
- Indexes: source_id, source_type, enabled
- Unique constraint: source_id

### llm_logs
- LLM API call logging for monitoring and cost tracking
- Columns: id (UUID), provider, model, prompt_tokens, completion_tokens, total_tokens, latency_ms, status, error_message, created_at
- Indexes: provider, model, status, created_at

## Notes

- All tables use UUID primary keys with `gen_random_uuid()` default
- Timestamps use timezone-aware DateTime columns
- JSONB columns are used for flexible data (credentials, alert_rules, schedule_config)
- Foreign key constraints with CASCADE DELETE ensure referential integrity
- Indexes are created on frequently queried columns for performance
