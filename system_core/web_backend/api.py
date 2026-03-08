"""
Web Backend API endpoints for dashboard and configuration management.

Provides REST APIs for:
- Dashboard metrics and system status
- Recent signals and trading history
- Configuration management
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.database import get_db
from system_core.database.models import (
    Signal, Trade, FetchSource, EAProfile, User, CircuitBreakerState
)
from system_core.auth.middleware import get_current_user
from system_core.config import get_logger
from system_core.web_backend.schemas import (
    DashboardMetrics,
    SystemStatus,
    SignalResponse,
    TradeResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    ConfigUpdateResponse,
    ErrorResponse
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["web_backend"])

@router.get(
    "/dashboard/metrics",
    response_model=DashboardMetrics,
    summary="Get dashboard metrics",
    description="""
Retrieve comprehensive dashboard metrics including data source status, AI processing queue,
trading positions, and performance statistics.

**Authentication Required**: Yes (JWT Bearer token)

**Response includes**:
- Active data sources count
- Fetch operation success rate (last 24 hours)
- AI processing queue depth
- Active trading positions
- Account balance
- Signal statistics (today)
- Trading performance (today)
    """,
    responses={
        200: {
            "description": "Dashboard metrics retrieved successfully",
            "model": DashboardMetrics
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DashboardMetrics:
    """
    Get dashboard metrics.
    
    Returns comprehensive metrics for the dashboard including data source status,
    AI processing queue depth, trading positions, and performance statistics.
    
    Requirements: 20.2, 21.1, 35.3, 35.4
    """
    try:
        from sqlalchemy import select
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Active data sources
        result = await db.execute(
            select(func.count(FetchSource.id)).where(FetchSource.enabled == True)
        )
        active_data_sources = result.scalar() or 0
        
        # Fetch success rate (placeholder - would need fetch logs)
        fetch_success_rate = 95.0  # TODO: Calculate from actual fetch logs
        
        # AI processing queue depth (placeholder - would query Redis)
        ai_processing_queue_depth = 0  # TODO: Query from Event Bus
        
        # Active positions
        result = await db.execute(
            select(func.count(Trade.id)).where(Trade.status == "open")
        )
        active_positions = result.scalar() or 0
        
        # Account balance (sum of all trading accounts)
        # TODO: Query from TradingAccount model when available
        account_balance = 10000.0  # Placeholder
        
        # Signals today
        result = await db.execute(
            select(func.count(Signal.id)).where(Signal.created_at >= today_start)
        )
        signals_today = result.scalar() or 0
        
        # High-value signals today (relevance_score > 70)
        result = await db.execute(
            select(func.count(Signal.id)).where(
                and_(
                    Signal.created_at >= today_start,
                    Signal.relevance_score > 70
                )
            )
        )
        high_value_signals_today = result.scalar() or 0
        
        # Trades today
        result = await db.execute(
            select(func.count(Trade.id)).where(Trade.created_at >= today_start)
        )
        trades_today = result.scalar() or 0
        
        # Win rate today
        result = await db.execute(
            select(func.count(Trade.id)).where(
                and_(
                    Trade.created_at >= today_start,
                    Trade.profit > 0
                )
            )
        )
        winning_trades = result.scalar() or 0
        
        win_rate_today = (winning_trades / trades_today * 100) if trades_today > 0 else 0.0
        
        metrics = DashboardMetrics(
            active_data_sources=active_data_sources,
            fetch_success_rate=fetch_success_rate,
            ai_processing_queue_depth=ai_processing_queue_depth,
            active_positions=active_positions,
            account_balance=account_balance,
            signals_today=signals_today,
            high_value_signals_today=high_value_signals_today,
            trades_today=trades_today,
            win_rate_today=round(win_rate_today, 2)
        )
        
        logger.info("dashboard_metrics_retrieved", user_id=str(current_user.id))
        return metrics
        
    except Exception as e:
        logger.error("dashboard_metrics_error", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard metrics")

@router.get(
    "/dashboard/system-status",
    response_model=SystemStatus,
    summary="Get system status",
    description="""
Retrieve overall system health status and individual component statuses.

**Authentication Required**: No (Public endpoint)

**Response includes**:
- Overall system status (healthy/degraded/unhealthy)
- System uptime
- Application version
- Individual component statuses (database, Redis, event bus, engines)
    """,
    responses={
        200: {
            "description": "System status retrieved successfully",
            "model": SystemStatus
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_system_status() -> SystemStatus:
    """
    Get system status.
    
    Returns overall system health and detailed component statuses.
    
    Requirements: 20.2, 21.1, 35.3, 35.4
    """
    try:
        # TODO: Implement actual component health checks
        # For now, return placeholder data
        
        components = {
            "database": {"status": "healthy", "latency_ms": 5},
            "redis": {"status": "healthy", "latency_ms": 2},
            "event_bus": {"status": "healthy", "queue_depth": 0},
            "fetch_engine": {"status": "healthy", "active_tasks": 0},
            "ai_engine": {"status": "healthy", "processing_rate": 0},
            "execution_engine": {"status": "healthy", "pending_signals": 0}
        }
        
        # Determine overall status
        statuses = [comp["status"] for comp in components.values()]
        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"
        
        status_response = SystemStatus(
            status=overall_status,
            uptime=0,  # TODO: Calculate actual uptime
            version="1.0.0",
            components=components,
            timestamp=datetime.utcnow().isoformat()
        )
        
        logger.info("system_status_retrieved")
        return status_response
        
    except Exception as e:
        logger.error("system_status_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")

@router.get(
    "/dashboard/recent-signals",
    response_model=list[SignalResponse],
    summary="Get recent high-value signals",
    description="""
Retrieve recent high-value signals (relevance score > 70) with AI analysis details.

**Authentication Required**: Yes (JWT Bearer token)

**Query Parameters**:
- `limit`: Maximum number of signals to return (default: 20, max: 100)

**Response includes**:
- Signal ID and source information
- AI relevance score and impact assessment
- Summary and suggested actions
- Related trading symbols
- Confidence score
    """,
    responses={
        200: {
            "description": "Recent signals retrieved successfully",
            "model": list[SignalResponse]
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_recent_signals(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of signals to return"
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of signals to skip for pagination"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[SignalResponse]:
    """
    Get recent high-value signals.
    
    Returns list of recent signals with AI analysis details.
    
    Requirements: 20.6, 21.1, 35.3, 35.4
    """
    try:
        from sqlalchemy import select
        
        result = await db.execute(
            select(Signal)
            .where(Signal.relevance_score > 70)
            .order_by(desc(Signal.created_at))
            .limit(limit)
            .offset(offset)
        )
        signals = result.scalars().all()
        
        result_list = []
        for signal in signals:
            result_list.append(SignalResponse(
                id=str(signal.id),
                source=signal.source,
                source_type=signal.source_type,
                data_type=signal.data_type,
                relevance_score=signal.relevance_score,
                potential_impact=signal.potential_impact,
                summary=signal.summary,
                suggested_actions=signal.suggested_actions,
                related_symbols=signal.related_symbols,
                confidence=float(signal.confidence) if signal.confidence else None,
                created_at=signal.created_at.isoformat()
            ))
        
        logger.info("recent_signals_retrieved", count=len(result_list), user_id=str(current_user.id))
        return result_list
        
    except Exception as e:
        logger.error("recent_signals_error", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=500, detail="Failed to retrieve recent signals")

@router.get(
    "/trades",
    response_model=list[TradeResponse],
    summary="Get trading history",
    description="""
Retrieve trading history with optional filters.

**Authentication Required**: Yes (JWT Bearer token)

**Query Parameters**:
- `start_date`: Filter trades from this date (ISO 8601 format)
- `end_date`: Filter trades until this date (ISO 8601 format)
- `symbol`: Filter by trading symbol (e.g., "EUR/USD")
- `limit`: Maximum number of trades to return (default: 50, max: 500)

**Response includes**:
- Trade ID and order ID
- Symbol, direction, and volume
- Entry/exit prices
- Stop loss and take profit levels
- Profit/loss
- Trade status and timestamps
    """,
    responses={
        200: {
            "description": "Trades retrieved successfully",
            "model": list[TradeResponse]
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_trades(
    start_date: Optional[datetime] = Query(
        default=None,
        description="Filter trades from this date"
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="Filter trades until this date"
    ),
    symbol: Optional[str] = Query(
        default=None,
        description="Filter by trading symbol"
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of trades to return"
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of trades to skip for pagination"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[TradeResponse]:
    """
    Get trading history with filters.
    
    Returns list of trades matching the specified filters.
    
    Requirements: 20.5, 21.3, 35.3, 35.4
    """
    try:
        from sqlalchemy import select
        
        query = select(Trade)
        
        # Apply filters
        if start_date:
            query = query.where(Trade.created_at >= start_date)
        if end_date:
            query = query.where(Trade.created_at <= end_date)
        if symbol:
            query = query.where(Trade.symbol == symbol.upper())
        
        # Order by most recent first
        query = query.order_by(desc(Trade.created_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        trades = result.scalars().all()
        
        result_list = []
        for trade in trades:
            result_list.append(TradeResponse(
                id=str(trade.id),
                order_id=trade.broker_order_id,
                symbol=trade.symbol,
                direction=trade.direction,
                volume=float(trade.volume),
                entry_price=float(trade.entry_price) if trade.entry_price else None,
                exit_price=float(trade.execution_price) if trade.execution_price else None,
                stop_loss=float(trade.stop_loss) if trade.stop_loss else None,
                take_profit=float(trade.take_profit) if trade.take_profit else None,
                profit=float(trade.pnl) if trade.pnl else None,
                status=trade.status,
                created_at=trade.created_at.isoformat(),
                closed_at=trade.closed_at.isoformat() if trade.closed_at else None,
                ea_profile_id=str(trade.ea_profile_id) if trade.ea_profile_id else None
            ))
        
        logger.info("trades_retrieved", count=len(result_list), user_id=str(current_user.id))
        return result_list
        
    except Exception as e:
        logger.error("trades_retrieval_error", error=str(e), user_id=str(current_user.id))
        raise HTTPException(status_code=500, detail="Failed to retrieve trades")

@router.get(
    "/trades/{trade_id}",
    response_model=TradeResponse,
    summary="Get trade by ID",
    description="""
Retrieve detailed information for a specific trade.

**Authentication Required**: Yes (JWT Bearer token)

**Path Parameters**:
- `trade_id`: Trade UUID

**Response includes**:
- Complete trade details
- Entry/exit prices
- Stop loss and take profit levels
- Profit/loss
- Associated EA profile
    """,
    responses={
        200: {
            "description": "Trade retrieved successfully",
            "model": TradeResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        404: {
            "description": "Trade not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_trade_by_id(
    trade_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> TradeResponse:
    """
    Get individual trade details.
    
    Returns detailed information for a specific trade.
    
    Requirements: 20.5, 21.3, 35.3, 35.4
    """
    try:
        from sqlalchemy import select
        
        result = await db.execute(select(Trade).where(Trade.id == trade_id))
        trade = result.scalar_one_or_none()
        
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        
        result_data = TradeResponse(
            id=str(trade.id),
            order_id=trade.broker_order_id,
            symbol=trade.symbol,
            direction=trade.direction,
            volume=float(trade.volume),
            entry_price=float(trade.entry_price) if trade.entry_price else None,
            exit_price=float(trade.execution_price) if trade.execution_price else None,
            stop_loss=float(trade.stop_loss) if trade.stop_loss else None,
            take_profit=float(trade.take_profit) if trade.take_profit else None,
            profit=float(trade.pnl) if trade.pnl else None,
            status=trade.status,
            created_at=trade.created_at.isoformat(),
            closed_at=trade.closed_at.isoformat() if trade.closed_at else None,
            ea_profile_id=str(trade.ea_profile_id) if trade.ea_profile_id else None
        )
        
        logger.info("trade_retrieved", trade_id=str(trade_id), user_id=str(current_user.id))
        return result_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("trade_retrieval_error", error=str(e), trade_id=str(trade_id))
        raise HTTPException(status_code=500, detail="Failed to retrieve trade")

@router.get(
    "/config",
    response_model=list[str],
    summary="List available configuration files",
    description="""
List all available configuration files that can be retrieved or updated.

**Authentication Required**: Yes (JWT Bearer token)

**Response includes**:
- List of configuration file names
    """,
    responses={
        200: {
            "description": "Configuration files listed successfully",
            "model": list[str]
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        }
    }
)
async def list_configs(
    current_user: User = Depends(get_current_user)
) -> list[str]:
    """
    List available configuration files.
    
    Returns list of configuration file names that can be accessed.
    
    Requirements: 20.4, 21.4, 35.3, 35.4
    """
    allowed_files = [
        "fetch_sources.yaml",
        "llm_config.yaml",
        "push_config.yaml",
        "prompt_templates.yaml",
        "vector_db.yaml",
        "event_bus.yaml",
        "retention_policy.yaml",
        "accounts.yaml",
        "ea_config.yaml",
        "bot_commands.yaml"
    ]
    
    logger.info("config_list_retrieved", user_id=str(current_user.id))
    return allowed_files

@router.get(
    "/config/{file_name}",
    response_model=ConfigResponse,
    summary="Get configuration file",
    description="""
Retrieve a configuration file's content.

**Authentication Required**: Yes (JWT Bearer token)

**Path Parameters**:
- `file_name`: Configuration file name (e.g., "fetch_sources.yaml")

**Allowed Files**:
- fetch_sources.yaml
- llm_config.yaml
- push_config.yaml
- prompt_templates.yaml
- vector_db.yaml
- event_bus.yaml
- retention_policy.yaml
- accounts.yaml
- ea_config.yaml
- bot_commands.yaml

**Response includes**:
- Raw file content
- Parsed YAML structure
- Last modification timestamp
    """,
    responses={
        200: {
            "description": "Configuration retrieved successfully",
            "model": ConfigResponse
        },
        400: {
            "description": "Invalid file name or file not accessible",
            "model": ErrorResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        404: {
            "description": "Configuration file not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def get_config(
    file_name: str,
    current_user: User = Depends(get_current_user)
) -> ConfigResponse:
    """
    Load configuration file.
    
    Returns the content and parsed structure of a configuration file.
    
    Requirements: 20.4, 21.4, 35.3, 35.4
    """
    from pathlib import Path
    import yaml
    
    try:
        settings = get_settings()
        
        # Validate file name to prevent directory traversal
        if ".." in file_name or "/" in file_name or "\\" in file_name:
            raise HTTPException(status_code=400, detail="Invalid file name")
        
        # Allowed config files
        allowed_files = [
            "fetch_sources.yaml",
            "llm_config.yaml",
            "push_config.yaml",
            "prompt_templates.yaml",
            "vector_db.yaml",
            "event_bus.yaml",
            "retention_policy.yaml",
            "accounts.yaml",
            "ea_config.yaml",
            "bot_commands.yaml"
        ]
        
        if file_name not in allowed_files:
            raise HTTPException(status_code=400, detail=f"File '{file_name}' is not accessible")
        
        config_path = Path(settings.config_dir) / file_name
        
        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"Configuration file '{file_name}' not found")
        
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parse YAML to validate syntax
        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as e:
            logger.warning("config_parse_warning", file_name=file_name, error=str(e))
            parsed = None
        
        logger.info("config_retrieved", file_name=file_name, user_id=str(current_user.id))
        
        return ConfigResponse(
            file_name=file_name,
            content=content,
            parsed=parsed,
            last_modified=datetime.fromtimestamp(config_path.stat().st_mtime).isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("config_retrieval_error", file_name=file_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration")

@router.put(
    "/config/{file_name}",
    response_model=ConfigUpdateResponse,
    summary="Update configuration file",
    description="""
Update a configuration file with new content.

**Authentication Required**: Yes (JWT Bearer token)

**Path Parameters**:
- `file_name`: Configuration file name

**Request Body**:
- `content`: New configuration content in YAML format

**Behavior**:
- Validates YAML syntax before saving
- Creates backup of existing file
- Returns validation errors with line/column information
- Triggers hot-reload of configuration

**Note**: Invalid YAML will be rejected with detailed error information.
    """,
    responses={
        200: {
            "description": "Configuration updated successfully",
            "model": ConfigUpdateResponse
        },
        400: {
            "description": "Invalid file name, file not accessible, or invalid YAML syntax",
            "model": ErrorResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def update_config(
    file_name: str,
    request: ConfigUpdateRequest = Body(...),
    current_user: User = Depends(get_current_user)
) -> ConfigUpdateResponse:
    """
    Save configuration file.
    
    Validates and saves new configuration content with automatic backup.
    
    Requirements: 20.4, 21.4, 21.5, 35.3, 35.4
    """
    from pathlib import Path
    import yaml
    import tempfile
    import shutil
    
    content = request.content
    
    try:
        settings = get_settings()
        
        # Validate file name
        if ".." in file_name or "/" in file_name or "\\" in file_name:
            raise HTTPException(status_code=400, detail="Invalid file name")
        
        allowed_files = [
            "fetch_sources.yaml",
            "llm_config.yaml",
            "push_config.yaml",
            "prompt_templates.yaml",
            "vector_db.yaml",
            "event_bus.yaml",
            "retention_policy.yaml",
            "accounts.yaml",
            "ea_config.yaml",
            "bot_commands.yaml"
        ]
        
        if file_name not in allowed_files:
            raise HTTPException(status_code=400, detail=f"File '{file_name}' is not accessible")
        
        # Validate YAML syntax
        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as e:
            error_details = {
                "error": "ValidationError",
                "message": "Invalid YAML syntax",
                "details": {
                    "line": getattr(e, "problem_mark", None).line + 1 if hasattr(e, "problem_mark") else None,
                    "column": getattr(e, "problem_mark", None).column + 1 if hasattr(e, "problem_mark") else None,
                    "problem": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            logger.warning("config_validation_failed", file_name=file_name, error=str(e))
            raise HTTPException(status_code=400, detail=error_details)
        
        # Save configuration with atomic write
        config_path = Path(settings.config_dir) / file_name
        
        # Ensure config directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            dir=config_path.parent,
            encoding='utf-8',
            suffix='.tmp'
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        
        try:
            # Create backup if file exists
            if config_path.exists():
                backup_path = config_path.with_suffix(f".yaml.backup.{int(datetime.utcnow().timestamp())}")
                shutil.copy2(config_path, backup_path)
                logger.info("config_backup_created", file_name=file_name, backup=str(backup_path))
            
            # Atomic replace
            shutil.move(str(tmp_path), str(config_path))
            
            logger.info("config_updated", file_name=file_name, user_id=str(current_user.id))
            
            return ConfigUpdateResponse(
                success=True,
                message=f"Configuration '{file_name}' updated successfully",
                file_name=file_name,
                timestamp=datetime.utcnow().isoformat()
            )
        except Exception as e:
            # Clean up temp file on error
            if tmp_path.exists():
                tmp_path.unlink()
            raise
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("config_update_error", file_name=file_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update configuration")
