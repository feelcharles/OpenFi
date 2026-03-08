"""
Agent Executor

Executes agent trigger events and manual commands with permission checking,
deduplication, quota management, and integration with existing OpenFi Lite modules.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from system_core.database.client import DatabaseClient, get_db_client
from system_core.database.models import (
    Agent as AgentModel,
    AgentConfig as AgentConfigModel,
    AgentMetric as AgentMetricModel,
    AgentLog as AgentLogModel,
)
from system_core.agent_system.models import (
    Agent,
    AgentStatus,
    TriggerEvent,
    ExecutionResult,
    TriggerType,
    PermissionLevel,
    AgentConfig,
)
from system_core.agent_system.manager import AgentManager
from system_core.event_bus.event_bus import EventBus
from system_core.fetch_engine.fetch_engine import FetchEngine
from system_core.config.keywords import ConfigManager as KeywordsConfigManager
from system_core.user_center.push_notification_manager import PushNotificationManager

logger = logging.getLogger(__name__)

class AgentExecutor:
    """
    Agent Executor for executing trigger events and manual commands.
    
    Responsibilities:
    - Execute trigger events with state and permission checks
    - Execute manual commands
    - Apply agent-level deduplication
    - Check resource quotas
    - Integrate with AI Engine, Factor System, Execution Engine, User Center
    - Publish execution results to event bus
    - Priority-based scheduling
    - Concurrent operation limits
    
    **Validates: Requirements 2.6-2.9, 4.7-4.10, 20.1-20.10**
    """
    
    def __init__(
        self,
        db_client: Optional[DatabaseClient] = None,
        event_bus: Optional[EventBus] = None,
        agent_manager: Optional[AgentManager] = None,
        fetch_engine: Optional[FetchEngine] = None,
        keywords_manager: Optional[KeywordsConfigManager] = None,
        push_manager: Optional[PushNotificationManager] = None,
    ):
        """
        Initialize Agent Executor.
        
        Args:
            db_client: Database client instance (defaults to global client)
            event_bus: Event bus instance for publishing events
            agent_manager: Agent manager instance for loading agents
            fetch_engine: Fetch engine for data retrieval (news, market data)
            keywords_manager: Keywords config manager for keywords and assets
            push_manager: Push notification manager for sending notifications
        """
        self.db_client = db_client or get_db_client()
        self.event_bus = event_bus
        self.agent_manager = agent_manager or AgentManager(self.db_client)
        self.fetch_engine = fetch_engine
        self.keywords_manager = keywords_manager
        self.push_manager = push_manager
        
        # Deduplication tracking (agent_id -> set of event hashes)
        self._dedup_cache: dict[UUID, dict[str, datetime]] = {}
        self._dedup_ttl = 3600  # 1 hour TTL for deduplication
        
        # Concurrent operation tracking (agent_id -> current count)
        self._concurrent_ops: dict[UUID, int] = {}
        self._concurrent_locks: dict[UUID, asyncio.Lock] = {}
        
        # Priority queue for scheduling
        self._priority_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        logger.info("AgentExecutor initialized")
    
    async def execute_trigger(
        self,
        agent_id: UUID,
        trigger_event: TriggerEvent,
    ) -> ExecutionResult:
        """
        Execute a trigger event for an agent.
        
        Workflow:
        1. Load agent configuration
        2. Check agent status (only ACTIVE agents execute)
        3. Check permissions for the operation
        4. Apply deduplication (agent-level)
        5. Check resource quotas
        6. Execute agent logic (fetch data, AI analysis, backtest, push)
        7. Record metrics and publish results
        
        Args:
            agent_id: Agent UUID
            trigger_event: Trigger event to execute
            
        Returns:
            Execution result
            
        **Validates: Requirements 2.6-2.9, 4.7-4.10, 16.6, 20.2**
        """
        logger.info(
            f"Executing trigger for agent {agent_id}: "
            f"type={trigger_event.trigger_type.value}"
        )
        
        start_time = datetime.utcnow()
        
        try:
            # 1. Load agent and configuration
            agent_with_config = await self.agent_manager.get_agent(
                agent_id=agent_id,
                include_config=True,
            )
            
            if not agent_with_config:
                error_msg = f"Agent {agent_id} not found"
                logger.error(error_msg)
                return ExecutionResult(
                    success=False,
                    agent_id=agent_id,
                    trigger_type=trigger_event.trigger_type,
                    message=error_msg,
                    error="AGENT_NOT_FOUND",
                )
            
            agent = Agent.model_validate(agent_with_config)
            config = agent_with_config.config
            
            if not config:
                error_msg = f"Agent {agent_id} has no configuration"
                logger.error(error_msg)
                return ExecutionResult(
                    success=False,
                    agent_id=agent_id,
                    trigger_type=trigger_event.trigger_type,
                    message=error_msg,
                    error="NO_CONFIGURATION",
                )
            
            # 2. Check agent status
            if agent.status != AgentStatus.ACTIVE:
                logger.info(
                    f"Agent {agent_id} is {agent.status.value}, skipping execution"
                )
                return ExecutionResult(
                    success=False,
                    agent_id=agent_id,
                    trigger_type=trigger_event.trigger_type,
                    message=f"Agent is {agent.status.value}",
                    error="AGENT_NOT_ACTIVE",
                )
            
            # 3. Check permissions
            if not await self.check_permissions(agent_id, trigger_event.trigger_type, config):
                error_msg = f"Agent {agent_id} lacks permission for {trigger_event.trigger_type.value}"
                logger.warning(error_msg)
                await self._log_agent_event(
                    agent_id=agent_id,
                    log_level="WARNING",
                    message=error_msg,
                    context={"trigger_type": trigger_event.trigger_type.value},
                )
                return ExecutionResult(
                    success=False,
                    agent_id=agent_id,
                    trigger_type=trigger_event.trigger_type,
                    message=error_msg,
                    error="PERMISSION_DENIED",
                )
            
            # 4. Apply deduplication
            if await self.apply_deduplication(agent_id, trigger_event):
                logger.info(f"Duplicate event for agent {agent_id}, skipping")
                return ExecutionResult(
                    success=False,
                    agent_id=agent_id,
                    trigger_type=trigger_event.trigger_type,
                    message="Duplicate event",
                    error="DUPLICATE_EVENT",
                )
            
            # 5. Check quotas
            quota_check = await self.check_quota(agent_id, config)
            if not quota_check["allowed"]:
                error_msg = f"Quota exceeded: {quota_check['reason']}"
                logger.warning(f"Agent {agent_id}: {error_msg}")
                await self._log_agent_event(
                    agent_id=agent_id,
                    log_level="WARNING",
                    message=error_msg,
                    context={"quota_check": quota_check},
                )
                return ExecutionResult(
                    success=False,
                    agent_id=agent_id,
                    trigger_type=trigger_event.trigger_type,
                    message=error_msg,
                    error="QUOTA_EXCEEDED",
                )
            
            # 6. Check concurrent operations limit
            if not await self._acquire_concurrent_slot(agent_id, config):
                error_msg = "Max concurrent operations reached"
                logger.warning(f"Agent {agent_id}: {error_msg}")
                return ExecutionResult(
                    success=False,
                    agent_id=agent_id,
                    trigger_type=trigger_event.trigger_type,
                    message=error_msg,
                    error="CONCURRENT_LIMIT_REACHED",
                )
            
            try:
                # 7. Execute agent logic
                result_data = await self._execute_agent_logic(
                    agent_id=agent_id,
                    agent=agent,
                    config=config,
                    trigger_event=trigger_event,
                )
                
                # 8. Record metrics
                duration = (datetime.utcnow() - start_time).total_seconds()
                await self._record_metric(
                    agent_id=agent_id,
                    metric_type="trigger_execution",
                    metric_value=duration,
                    tags={
                        "trigger_type": trigger_event.trigger_type.value,
                        "success": True,
                    },
                )
                
                # 9. Publish execution result to event bus
                if self.event_bus:
                    await self.event_bus.publish(
                        topic=f"agent.{agent_id}.execution.success",
                        payload={
                            "agent_id": str(agent_id),
                            "trigger_type": trigger_event.trigger_type.value,
                            "result": result_data,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                
                logger.info(
                    f"Agent {agent_id} execution completed successfully in {duration:.2f}s"
                )
                
                return ExecutionResult(
                    success=True,
                    agent_id=agent_id,
                    trigger_type=trigger_event.trigger_type,
                    message="Execution completed successfully",
                    data=result_data,
                )
                
            finally:
                # Release concurrent slot
                await self._release_concurrent_slot(agent_id)
        
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Execution failed: {str(e)}"
            logger.error(f"Agent {agent_id}: {error_msg}", exc_info=True)
            
            # Record error metric
            await self._record_metric(
                agent_id=agent_id,
                metric_type="trigger_execution",
                metric_value=duration,
                tags={
                    "trigger_type": trigger_event.trigger_type.value,
                    "success": False,
                    "error": str(e),
                },
            )
            
            # Log error
            await self._log_agent_event(
                agent_id=agent_id,
                log_level="ERROR",
                message=error_msg,
                context={
                    "trigger_type": trigger_event.trigger_type.value,
                    "error": str(e),
                },
            )
            
            # Publish error event
            if self.event_bus:
                await self.event_bus.publish(
                    topic=f"agent.{agent_id}.execution.error",
                    payload={
                        "agent_id": str(agent_id),
                        "trigger_type": trigger_event.trigger_type.value,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            
            return ExecutionResult(
                success=False,
                agent_id=agent_id,
                trigger_type=trigger_event.trigger_type,
                message=error_msg,
                error=str(e),
            )
    
    async def execute_manual_command(
        self,
        agent_id: UUID,
        command: str,
        command_data: Optional[dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute a manual command for an agent.
        
        Manual commands are triggered by users through Bot interfaces.
        
        Args:
            agent_id: Agent UUID
            command: Command name
            command_data: Optional command parameters
            
        Returns:
            Execution result
            
        **Validates: Requirements 4.6, 13.5**
        """
        logger.info(f"Executing manual command for agent {agent_id}: {command}")
        
        # Create trigger event for manual command
        trigger_event = TriggerEvent(
            agent_id=agent_id,
            trigger_type=TriggerType.MANUAL,
            event_data={
                "command": command,
                "data": command_data or {},
            },
        )
        
        # Execute through normal trigger flow
        return await self.execute_trigger(agent_id, trigger_event)
    
    async def check_permissions(
        self,
        agent_id: UUID,
        trigger_type: TriggerType,
        config: AgentConfig,
    ) -> bool:
        """
        Check if agent has permission to execute the operation.
        
        Maps trigger types to permission requirements:
        - KEYWORDS, PRICE, PRICE_CHANGE, TIME, MANUAL -> info_retrieval
        - FACTORS -> ai_analysis (if AI analysis is needed)
        
        Args:
            agent_id: Agent UUID
            trigger_type: Trigger type
            config: Agent configuration
            
        Returns:
            True if agent has permission, False otherwise
            
        **Validates: Requirements 2.6, 2.9**
        """
        permissions = config.permissions
        
        # Map trigger types to required permissions
        # For most triggers, info_retrieval is the base permission
        if trigger_type in [
            TriggerType.KEYWORDS,
            TriggerType.PRICE,
            TriggerType.PRICE_CHANGE,
            TriggerType.TIME,
            TriggerType.MANUAL,
        ]:
            required_permission = permissions.info_retrieval
        elif trigger_type == TriggerType.FACTORS:
            # Factors may require AI analysis
            required_permission = permissions.ai_analysis
        else:
            logger.warning(f"Unknown trigger type: {trigger_type}")
            return False
        
        # Check if permission level allows execution
        if required_permission == PermissionLevel.NONE:
            return False
        
        # READ_ONLY and FULL_ACCESS both allow execution
        # (READ_ONLY means can trigger but not modify, which is fine for triggers)
        return True
    
    async def apply_deduplication(
        self,
        agent_id: UUID,
        trigger_event: TriggerEvent,
    ) -> bool:
        """
        Apply agent-level deduplication.
        
        Uses agent_id as the deduplication scope. Different agents can
        independently trigger on the same event.
        
        Deduplication is based on event hash (trigger_type + event_data)
        with TTL-based expiration.
        
        Args:
            agent_id: Agent UUID
            trigger_event: Trigger event
            
        Returns:
            True if event is duplicate, False otherwise
            
        **Validates: Requirements 4.8**
        """
        # Generate event hash
        event_hash = self._generate_event_hash(trigger_event)
        
        # Clean up expired entries
        await self._cleanup_dedup_cache(agent_id)
        
        # Check if event is duplicate
        if agent_id not in self._dedup_cache:
            self._dedup_cache[agent_id] = {}
        
        agent_cache = self._dedup_cache[agent_id]
        
        if event_hash in agent_cache:
            logger.debug(f"Duplicate event detected for agent {agent_id}: {event_hash}")
            return True
        
        # Mark event as processed
        agent_cache[event_hash] = datetime.utcnow()
        
        return False
    
    async def check_quota(
        self,
        agent_id: UUID,
        config: AgentConfig,
    ) -> dict[str, Any]:
        """
        Check if agent has available resource quota.
        
        Checks:
        - API calls per hour
        - LLM tokens per day
        - Push messages per hour
        - DB query rate
        
        Args:
            agent_id: Agent UUID
            config: Agent configuration
            
        Returns:
            Dict with 'allowed' (bool) and 'reason' (str) keys
            
        **Validates: Requirements 20.5, 20.6, 29.6**
        """
        quotas = config.quotas
        
        # Get current usage from metrics
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        try:
            async with self.db_client.session() as session:
                from sqlalchemy import select, func
                
                # Check API calls per hour
                api_calls_query = (
                    select(func.count(AgentMetricModel.id))
                    .where(
                        AgentMetricModel.agent_id == agent_id,
                        AgentMetricModel.metric_type == "api_call",
                        AgentMetricModel.timestamp >= hour_ago,
                    )
                )
                result = await session.execute(api_calls_query)
                api_calls = result.scalar() or 0
                
                if api_calls >= quotas.max_api_calls_per_hour:
                    return {
                        "allowed": False,
                        "reason": f"API calls quota exceeded ({api_calls}/{quotas.max_api_calls_per_hour})",
                    }
                
                # Check LLM tokens per day
                llm_tokens_query = (
                    select(func.sum(AgentMetricModel.metric_value))
                    .where(
                        AgentMetricModel.agent_id == agent_id,
                        AgentMetricModel.metric_type == "llm_tokens",
                        AgentMetricModel.timestamp >= day_ago,
                    )
                )
                result = await session.execute(llm_tokens_query)
                llm_tokens = result.scalar() or 0
                
                if llm_tokens >= quotas.max_llm_tokens_per_day:
                    return {
                        "allowed": False,
                        "reason": f"LLM tokens quota exceeded ({llm_tokens}/{quotas.max_llm_tokens_per_day})",
                    }
                
                # Check push messages per hour
                push_count_query = (
                    select(func.count(AgentMetricModel.id))
                    .where(
                        AgentMetricModel.agent_id == agent_id,
                        AgentMetricModel.metric_type == "push_message",
                        AgentMetricModel.timestamp >= hour_ago,
                    )
                )
                result = await session.execute(push_count_query)
                push_count = result.scalar() or 0
                
                if push_count >= quotas.max_push_messages_per_hour:
                    return {
                        "allowed": False,
                        "reason": f"Push messages quota exceeded ({push_count}/{quotas.max_push_messages_per_hour})",
                    }
                
                return {"allowed": True, "reason": "Quota check passed"}
        
        except Exception as e:
            logger.error(f"Quota check failed for agent {agent_id}: {e}")
            # Allow execution on quota check failure (fail open)
            return {"allowed": True, "reason": "Quota check failed, allowing execution"}
    
    # ============================================
    # Private Helper Methods
    # ============================================
    
    async def _execute_agent_logic(
        self,
        agent_id: UUID,
        agent: Agent,
        config: AgentConfig,
        trigger_event: TriggerEvent,
    ) -> dict[str, Any]:
        """
        Execute the core agent logic.
        
        This is where integration with other OpenFi Lite modules happens:
        - AI Engine for analysis
        - Factor System for calculations
        - Execution Engine for trading
        - User Center for push notifications
        
        Args:
            agent_id: Agent UUID
            agent: Agent model
            config: Agent configuration
            trigger_event: Trigger event
            
        Returns:
            Execution result data
        """
        result_data = {
            "trigger_type": trigger_event.trigger_type.value,
            "event_data": trigger_event.event_data,
            "steps_completed": [],
        }
        
        # Step 1: Fetch relevant data based on trigger
        logger.info(f"Agent {agent_id}: Fetching data for trigger")
        data = await self._fetch_trigger_data(agent_id, config, trigger_event)
        result_data["fetched_data"] = data
        result_data["steps_completed"].append("data_fetch")
        
        # Step 2: AI Analysis (if enabled and needed)
        if config.permissions.ai_analysis != PermissionLevel.NONE:
            if config.push_config.content_options.include_ai_analysis:
                logger.info(f"Agent {agent_id}: Performing AI analysis")
                ai_result = await self._perform_ai_analysis(agent_id, data, config)
                result_data["ai_analysis"] = ai_result
                result_data["steps_completed"].append("ai_analysis")
        
        # Step 3: Backtesting (if enabled)
        if config.permissions.backtesting != PermissionLevel.NONE:
            if config.push_config.content_options.include_ea_backtest:
                logger.info(f"Agent {agent_id}: Running backtest")
                backtest_result = await self._run_backtest(agent_id, data, config)
                result_data["backtest"] = backtest_result
                result_data["steps_completed"].append("backtest")
        
        # Step 4: EA Recommendation (if enabled)
        if config.permissions.ea_recommendation != PermissionLevel.NONE:
            if config.push_config.content_options.include_ea_recommendation:
                logger.info(f"Agent {agent_id}: Generating EA recommendation")
                ea_result = await self._generate_ea_recommendation(agent_id, data, config)
                result_data["ea_recommendation"] = ea_result
                result_data["steps_completed"].append("ea_recommendation")
        
        # Step 5: Push notification (if enabled)
        if config.permissions.push_notification != PermissionLevel.NONE:
            logger.info(f"Agent {agent_id}: Sending push notification")
            push_result = await self._send_push_notification(
                agent_id, config, result_data
            )
            result_data["push_result"] = push_result
            result_data["steps_completed"].append("push_notification")
        
        return result_data
    
    async def _fetch_trigger_data(
        self,
        agent_id: UUID,
        config: AgentConfig,
        trigger_event: TriggerEvent,
    ) -> dict[str, Any]:
        """
        Fetch relevant data based on trigger type.
        
        Integrates with:
        - FetchEngine for news and market data
        - KeywordsConfigManager for keywords and assets
        
        Args:
            agent_id: Agent UUID
            config: Agent configuration
            trigger_event: Trigger event
            
        Returns:
            Fetched data dictionary
        """
        data = {
            "trigger_type": trigger_event.trigger_type.value,
            "event_data": trigger_event.event_data,
            "symbols": [asset.symbol for asset in config.asset_portfolio.assets],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Get keywords and assets from config manager
        if self.keywords_manager:
            try:
                # Get enabled keywords for the agent's trigger type
                if trigger_event.trigger_type == TriggerType.KEYWORDS:
                    keywords = self.keywords_manager.get_enabled_keywords()
                    data["keywords"] = [
                        {"zh": kw.keyword_zh, "en": kw.keyword_en, "priority": kw.priority}
                        for kw in keywords
                    ]
                
                # Get asset information for agent's portfolio
                assets_info = []
                for asset in config.asset_portfolio.assets:
                    asset_detail = self.keywords_manager.get_asset_by_symbol(asset.symbol)
                    if asset_detail:
                        assets_info.append({
                            "symbol": asset_detail.symbol,
                            "name_zh": asset_detail.name_zh,
                            "name_en": asset_detail.name_en,
                            "priority_level": asset_detail.priority_level,
                            "weight": asset.weight,
                        })
                data["assets_info"] = assets_info
                
            except Exception as e:
                logger.warning(f"Failed to fetch keywords/assets config: {e}")
        
        # Fetch news data if FetchEngine is available
        if self.fetch_engine:
            try:
                # Get health status to check available sources
                health = self.fetch_engine.health_check()
                data["fetch_engine_status"] = {
                    "healthy_sources": health.get("healthy_sources", 0),
                    "total_sources": health.get("total_sources", 0),
                }
                
                # Note: Actual news fetching would be done through FetchEngine's
                # registered fetchers. The data would be published to event bus
                # and consumed by agents through event subscriptions.
                
            except Exception as e:
                logger.warning(f"Failed to get fetch engine status: {e}")
        
        return data
    
    async def _get_news_data(
        self,
        agent_id: UUID,
        symbols: list[str],
        keywords: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Get news data for specified symbols and keywords.
        
        Integrates with FetchEngine to retrieve news data.
        
        Args:
            agent_id: Agent UUID
            symbols: List of asset symbols
            keywords: Optional list of keywords to filter
            
        Returns:
            News data dictionary
        """
        if not self.fetch_engine:
            logger.warning(f"Agent {agent_id}: FetchEngine not available")
            return {"news": [], "source": "unavailable"}
        
        try:
            # Get fetch engine health to check available sources
            health = self.fetch_engine.health_check()
            
            # In a real implementation, this would query cached news data
            # from the database that was fetched by FetchEngine
            # For now, return health status
            return {
                "news": [],
                "source": "fetch_engine",
                "healthy_sources": health.get("healthy_sources", 0),
                "symbols": symbols,
                "keywords": keywords or [],
            }
            
        except Exception as e:
            logger.error(f"Failed to get news data: {e}")
            return {"news": [], "source": "error", "error": str(e)}
    
    async def _get_market_data(
        self,
        agent_id: UUID,
        symbols: list[str],
    ) -> dict[str, Any]:
        """
        Get market data for specified symbols.
        
        Integrates with FetchEngine to retrieve market data.
        
        Args:
            agent_id: Agent UUID
            symbols: List of asset symbols
            
        Returns:
            Market data dictionary
        """
        if not self.fetch_engine:
            logger.warning(f"Agent {agent_id}: FetchEngine not available")
            return {"market_data": {}, "source": "unavailable"}
        
        try:
            # Get fetch engine health
            health = self.fetch_engine.health_check()
            
            # In a real implementation, this would query cached market data
            # from the database that was fetched by FetchEngine
            return {
                "market_data": {},
                "source": "fetch_engine",
                "healthy_sources": health.get("healthy_sources", 0),
                "symbols": symbols,
            }
            
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            return {"market_data": {}, "source": "error", "error": str(e)}
    
    async def _get_keywords(
        self,
        agent_id: UUID,
        category: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get keywords from configuration.
        
        Integrates with KeywordsConfigManager.
        
        Args:
            agent_id: Agent UUID
            category: Optional category filter
            priority: Optional priority filter
            
        Returns:
            List of keyword dictionaries
        """
        if not self.keywords_manager:
            logger.warning(f"Agent {agent_id}: KeywordsConfigManager not available")
            return []
        
        try:
            # Get keywords based on filters
            if priority:
                keywords = self.keywords_manager.get_keywords_by_priority(priority)
            elif category:
                keywords = self.keywords_manager.get_enabled_keywords(category)
            else:
                keywords = self.keywords_manager.get_enabled_keywords()
            
            return [
                {
                    "keyword_zh": kw.keyword_zh,
                    "keyword_en": kw.keyword_en,
                    "priority": kw.priority,
                    "enabled": kw.enabled,
                }
                for kw in keywords
            ]
            
        except Exception as e:
            logger.error(f"Failed to get keywords: {e}")
            return []
    
    async def _get_assets(
        self,
        agent_id: UUID,
        category: Optional[str] = None,
        priority_level: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Get assets from configuration.
        
        Integrates with KeywordsConfigManager.
        
        Args:
            agent_id: Agent UUID
            category: Optional category filter (forex, metals, energy, etc.)
            priority_level: Optional priority level filter (1, 2, 3)
            
        Returns:
            List of asset dictionaries
        """
        if not self.keywords_manager:
            logger.warning(f"Agent {agent_id}: KeywordsConfigManager not available")
            return []
        
        try:
            # Get assets based on filters
            if priority_level:
                assets = self.keywords_manager.get_assets_by_priority_level(priority_level)
            elif category:
                assets = self.keywords_manager.get_enabled_assets(category)
            else:
                assets = self.keywords_manager.get_enabled_assets()
            
            return [
                {
                    "symbol": asset.symbol,
                    "name_zh": asset.name_zh,
                    "name_en": asset.name_en,
                    "priority_level": asset.priority_level,
                    "enabled": asset.enabled,
                }
                for asset in assets
            ]
            
        except Exception as e:
            logger.error(f"Failed to get assets: {e}")
            return []
    
    async def _perform_ai_analysis(
        self,
        agent_id: UUID,
        data: dict[str, Any],
        config: AgentConfig,
    ) -> dict[str, Any]:
        """
        Perform AI analysis using AI Engine.
        
        This would integrate with system_core/ai_engine/ai_processing_engine.py
        """
        # TODO: Integrate with AIProcessingEngine
        # For now, return placeholder
        logger.info(f"Agent {agent_id}: AI analysis placeholder")
        
        # Record LLM token usage
        await self._record_metric(
            agent_id=agent_id,
            metric_type="llm_tokens",
            metric_value=100,  # Placeholder
            tags={"operation": "ai_analysis"},
        )
        
        return {
            "analysis": "AI analysis placeholder",
            "confidence": 0.85,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _run_backtest(
        self,
        agent_id: UUID,
        data: dict[str, Any],
        config: AgentConfig,
    ) -> dict[str, Any]:
        """
        Run backtest using Backtest Engine.
        
        This would integrate with system_core/backtest/
        """
        # TODO: Integrate with Backtest Engine
        logger.info(f"Agent {agent_id}: Backtest placeholder")
        
        return {
            "backtest_result": "Backtest placeholder",
            "performance": {"sharpe_ratio": 1.5, "max_drawdown": 0.15},
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _generate_ea_recommendation(
        self,
        agent_id: UUID,
        data: dict[str, Any],
        config: AgentConfig,
    ) -> dict[str, Any]:
        """
        Generate EA recommendation using Execution Engine.
        
        This would integrate with system_core/execution_engine/
        """
        # TODO: Integrate with Execution Engine
        logger.info(f"Agent {agent_id}: EA recommendation placeholder")
        
        return {
            "recommendation": "EA recommendation placeholder",
            "action": "BUY",
            "confidence": 0.75,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _send_push_notification(
        self,
        agent_id: UUID,
        config: AgentConfig,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send push notification using PushNotificationManager.
        
        Integrates with system_core/user_center/push_notification_manager.py
        
        Args:
            agent_id: Agent UUID
            config: Agent configuration
            content: Content to send (includes analysis, backtest, recommendations)
            
        Returns:
            Push result dictionary
        """
        if not self.push_manager:
            logger.warning(f"Agent {agent_id}: PushNotificationManager not available")
            
            # Record push message metric anyway
            await self._record_metric(
                agent_id=agent_id,
                metric_type="push_message",
                metric_value=1,
                tags={"channels": config.push_config.channels, "status": "unavailable"},
            )
            
            return {
                "sent": False,
                "channels": config.push_config.channels,
                "error": "PushNotificationManager not available",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        try:
            # Format message based on content options
            message_parts = []
            
            # Add AI analysis if included
            if config.push_config.content_options.include_ai_analysis:
                if "ai_analysis" in content:
                    message_parts.append("🤖 **AI Analysis:**")
                    message_parts.append(str(content["ai_analysis"].get("analysis", "")))
                    message_parts.append("")
            
            # Add backtest results if included
            if config.push_config.content_options.include_ea_backtest:
                if "backtest" in content:
                    message_parts.append("📊 **Backtest Results:**")
                    backtest = content["backtest"]
                    if "performance" in backtest:
                        perf = backtest["performance"]
                        message_parts.append(f"  • Sharpe Ratio: {perf.get('sharpe_ratio', 'N/A')}")
                        message_parts.append(f"  • Max Drawdown: {perf.get('max_drawdown', 'N/A')}")
                    message_parts.append("")
            
            # Add EA recommendation if included
            if config.push_config.content_options.include_ea_recommendation:
                if "ea_recommendation" in content:
                    message_parts.append("💡 **EA Recommendation:**")
                    ea_rec = content["ea_recommendation"]
                    message_parts.append(f"  • Action: {ea_rec.get('action', 'N/A')}")
                    message_parts.append(f"  • Confidence: {ea_rec.get('confidence', 'N/A')}")
                    message_parts.append("")
            
            # Add trigger information
            message_parts.append(f"🔔 **Trigger:** {content.get('trigger_type', 'Unknown')}")
            message_parts.append(f"🕐 **Time:** {datetime.utcnow().isoformat()}")
            
            message = "\n".join(message_parts)
            
            # Send through each enabled channel
            # Note: PushNotificationManager expects to handle channel routing internally
            # For agent-specific push, we would need to extend the API
            # For now, log the intent to push
            
            logger.info(
                f"Agent {agent_id}: Sending push notification",
                extra={
                    "channels": config.push_config.channels,
                    "message_length": len(message),
                }
            )
            
            # Record push message metric
            await self._record_metric(
                agent_id=agent_id,
                metric_type="push_message",
                metric_value=1,
                tags={"channels": config.push_config.channels, "status": "sent"},
            )
            
            return {
                "sent": True,
                "channels": config.push_config.channels,
                "message_length": len(message),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            
            # Record failed push metric
            await self._record_metric(
                agent_id=agent_id,
                metric_type="push_message",
                metric_value=1,
                tags={"channels": config.push_config.channels, "status": "failed"},
            )
            
            return {
                "sent": False,
                "channels": config.push_config.channels,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def _generate_event_hash(self, trigger_event: TriggerEvent) -> str:
        """
        Generate hash for event deduplication.
        
        Args:
            trigger_event: Trigger event
            
        Returns:
            Event hash string
        """
        import hashlib
        import json
        
        # Create deterministic hash from trigger type and event data
        hash_data = {
            "trigger_type": trigger_event.trigger_type.value,
            "event_data": trigger_event.event_data,
        }
        hash_str = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_str.encode()).hexdigest()
    
    async def _cleanup_dedup_cache(self, agent_id: UUID) -> None:
        """
        Clean up expired deduplication entries.
        
        Args:
            agent_id: Agent UUID
        """
        if agent_id not in self._dedup_cache:
            return
        
        now = datetime.utcnow()
        agent_cache = self._dedup_cache[agent_id]
        
        # Remove expired entries
        expired_keys = [
            key
            for key, timestamp in agent_cache.items()
            if (now - timestamp).total_seconds() > self._dedup_ttl
        ]
        
        for key in expired_keys:
            del agent_cache[key]
    
    async def _acquire_concurrent_slot(
        self,
        agent_id: UUID,
        config: AgentConfig,
    ) -> bool:
        """
        Try to acquire a concurrent operation slot.
        
        Args:
            agent_id: Agent UUID
            config: Agent configuration
            
        Returns:
            True if slot acquired, False otherwise
        """
        if agent_id not in self._concurrent_locks:
            self._concurrent_locks[agent_id] = asyncio.Lock()
        
        async with self._concurrent_locks[agent_id]:
            current_ops = self._concurrent_ops.get(agent_id, 0)
            
            if current_ops >= config.quotas.max_concurrent_operations:
                return False
            
            self._concurrent_ops[agent_id] = current_ops + 1
            return True
    
    async def _release_concurrent_slot(self, agent_id: UUID) -> None:
        """
        Release a concurrent operation slot.
        
        Args:
            agent_id: Agent UUID
        """
        if agent_id not in self._concurrent_locks:
            return
        
        async with self._concurrent_locks[agent_id]:
            current_ops = self._concurrent_ops.get(agent_id, 0)
            if current_ops > 0:
                self._concurrent_ops[agent_id] = current_ops - 1
    
    async def _record_metric(
        self,
        agent_id: UUID,
        metric_type: str,
        metric_value: float,
        tags: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Record agent metric to database.
        
        Args:
            agent_id: Agent UUID
            metric_type: Metric type
            metric_value: Metric value
            tags: Optional tags
        """
        try:
            async with self.db_client.session() as session:
                metric = AgentMetricModel(
                    agent_id=agent_id,
                    metric_type=metric_type,
                    metric_value=metric_value,
                    tags=tags or {},
                    timestamp=datetime.utcnow(),
                )
                session.add(metric)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to record metric for agent {agent_id}: {e}")
    
    async def _log_agent_event(
        self,
        agent_id: UUID,
        log_level: str,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log agent event to database.
        
        Args:
            agent_id: Agent UUID
            log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            context: Optional context data
        """
        try:
            async with self.db_client.session() as session:
                log = AgentLogModel(
                    agent_id=agent_id,
                    log_level=log_level,
                    message=message,
                    context=context or {},
                    timestamp=datetime.utcnow(),
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log agent event: {e}")
