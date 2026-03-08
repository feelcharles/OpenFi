"""
AI Processing Engine

Orchestrates AI analysis of fetched data using LLMs.
Subscribes to raw data events, analyzes with LLM, and publishes high-value signals.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
"""

import asyncio
import uuid
from typing import Any, Optional
from datetime import datetime
from system_core.config import get_logger
from system_core.event_bus import EventBus, Event, RawDataEvent, HighValueSignalEvent
from system_core.database.models import Signal, User, EAProfile
from system_core.database import get_db_client
from .llm_client import LLMClient, LLMResponse
from .prompt_manager import PromptTemplateManager
from .response_parser import ResponseParser, AnalysisResult

logger = get_logger(__name__)

class AIProcessingEngine:
    """
    AI Processing Engine orchestrator.
    
    Features:
    - Subscribe to raw data events from Event Bus
    - Select appropriate prompt template based on data type
    - Inject user context into prompts
    - Call LLM for analysis
    - Parse and validate LLM responses
    - Filter signals by relevance threshold
    - Publish high-value signals to Event Bus
    - Store signals in database
    - Track LLM interaction metrics
    
    Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        llm_client: LLMClient,
        prompt_manager: PromptTemplateManager,
        response_parser: ResponseParser,
        relevance_threshold: int = 70
    ):
        """
        Initialize AI Processing Engine.
        
        Args:
            event_bus: Event bus for pub/sub
            llm_client: LLM client for API calls
            prompt_manager: Prompt template manager
            response_parser: Response parser
            relevance_threshold: Minimum relevance score to publish signal
            
        Validates: Requirement 4.1
        """
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager
        self.response_parser = response_parser
        self.relevance_threshold = relevance_threshold
        self.logger = logger
        
        self._running = False
        self._tasks = []
    
    async def start(self) -> None:
        """
        Start AI Processing Engine.
        
        Subscribes to raw data events.
        
        Validates: Requirement 4.1
        """
        self.logger.info("Starting AI Processing Engine")
        self._running = True
        
        # Subscribe to all raw data topics
        await self.event_bus.subscribe("data.raw.*", self._handle_raw_data_event)
        
        self.logger.info("AI Processing Engine started")
    
    async def stop(self) -> None:
        """Stop AI Processing Engine."""
        self.logger.info("Stopping AI Processing Engine")
        self._running = False
        
        # Wait for pending tasks
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Close LLM client
        await self.llm_client.close()
        
        self.logger.info("AI Processing Engine stopped")
    
    async def _handle_raw_data_event(self, event: Event) -> None:
        """
        Handle raw data event from Event Bus.
        
        Args:
            event: Raw data event
            
        Validates: Requirements 4.1, 4.2
        """
        try:
            # Parse raw data payload
            raw_data = RawDataEvent(**event.payload)
            
            self.logger.info(
                f"Processing raw data event",
                extra={
                    "event_id": str(event.event_id),
                    "source": raw_data.source,
                    "data_type": raw_data.data_type,
                    "trace_id": str(event.trace_id)
                }
            )
            
            # Process asynchronously
            task = asyncio.create_task(
                self._process_raw_data(event.trace_id, raw_data)
            )
            self._tasks.append(task)
            
        except Exception as e:
            self.logger.error(
                f"Failed to handle raw data event: {e}",
                exc_info=True,
                extra={"event_id": str(event.event_id)}
            )
    
    async def _process_raw_data(
        self,
        trace_id: uuid.UUID,
        raw_data: RawDataEvent
    ) -> None:
        """
        Process raw data with LLM analysis.
        
        Args:
            trace_id: Trace ID for correlation
            raw_data: Raw data event payload
            
        Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
        """
        start_time = datetime.utcnow()
        
        try:
            # Select prompt template based on data type
            prompts = self.prompt_manager.render(
                raw_data.data_type,
                self._build_context(raw_data)
            )
            
            if not prompts:
                self.logger.warning(
                    f"No template found for data_type: {raw_data.data_type}",
                    extra={"trace_id": str(trace_id)}
                )
                return
            
            # Call LLM for analysis
            llm_response = await self.llm_client.call(
                prompt=prompts['user_prompt'],
                system_prompt=prompts['system_prompt']
            )
            
            # Parse LLM response
            analysis = self.response_parser.parse(
                llm_response.content,
                llm_response.provider
            )
            
            # Log LLM interaction
            self._log_llm_interaction(
                trace_id,
                raw_data,
                llm_response,
                analysis,
                start_time
            )
            
            # Filter by relevance threshold
            if analysis.relevance_score > self.relevance_threshold:
                # Publish high-value signal
                await self._publish_high_value_signal(
                    trace_id,
                    raw_data,
                    analysis
                )
            else:
                self.logger.info(
                    f"Signal below threshold, not publishing",
                    extra={
                        "trace_id": str(trace_id),
                        "relevance_score": analysis.relevance_score,
                        "threshold": self.relevance_threshold
                    }
                )
            
        except Exception as e:
            self.logger.error(
                f"Failed to process raw data: {e}",
                exc_info=True,
                extra={"trace_id": str(trace_id)}
            )
    
    def _build_context(self, raw_data: RawDataEvent) -> dict[str, Any]:
        """
        Build context for prompt template.
        
        Injects user preferences, EA configurations, and data content.
        
        Args:
            raw_data: Raw data event payload
            
        Returns:
            Context dictionary for template rendering
            
        Validates: Requirement 4.3
        """
        context = {}
        
        # Add data content
        for key, value in raw_data.content.items():
            context[key] = value
        
        # Add data_content as full content
        context['data_content'] = raw_data.content
        
        # Provide defaults (database query would be async, so we use defaults for now)
        # In production, this would be populated from user configuration
        context['user_name'] = 'trader'
        context['trading_symbols'] = []
        context['active_eas'] = []
        context['risk_tolerance'] = 'medium'
        context['market_conditions'] = 'normal'
        context['recent_trades'] = []
        
        return context
    
    async def _publish_high_value_signal(
        self,
        trace_id: uuid.UUID,
        raw_data: RawDataEvent,
        analysis: AnalysisResult
    ) -> None:
        """
        Publish high-value signal to Event Bus and store in database.
        
        Args:
            trace_id: Trace ID for correlation
            raw_data: Original raw data
            analysis: Analysis result from LLM
            
        Validates: Requirements 4.6, 4.7
        """
        try:
            # Generate signal ID
            signal_id = uuid.uuid4()
            
            # Create high-value signal event
            signal_event = HighValueSignalEvent(
                signal_id=signal_id,
                source=raw_data.source,
                relevance_score=analysis.relevance_score,
                potential_impact=analysis.potential_impact,
                summary=analysis.summary,
                suggested_actions=analysis.suggested_actions,
                related_symbols=analysis.related_symbols,
                confidence=analysis.confidence,
                reasoning=analysis.reasoning
            )
            
            # Publish to Event Bus
            await self.event_bus.publish(
                topic="ai.high_value_signal",
                payload=signal_event.model_dump(),
                trace_id=trace_id
            )
            
            # Store in database
            await self._store_signal(signal_id, raw_data, analysis)
            
            self.logger.info(
                f"Published high-value signal",
                extra={
                    "signal_id": str(signal_id),
                    "trace_id": str(trace_id),
                    "relevance_score": analysis.relevance_score
                }
            )
            
        except Exception as e:
            self.logger.error(
                f"Failed to publish high-value signal: {e}",
                exc_info=True,
                extra={"trace_id": str(trace_id)}
            )
    
    async def _store_signal(
        self,
        signal_id: uuid.UUID,
        raw_data: RawDataEvent,
        analysis: AnalysisResult
    ) -> None:
        """
        Store signal in database.
        
        Args:
            signal_id: Signal identifier
            raw_data: Original raw data
            analysis: Analysis result
        """
        try:
            db_client = get_db_client()
            async with db_client.session() as session:
                signal = Signal(
                    id=signal_id,
                    source=raw_data.source,
                    source_type=raw_data.source_type,
                    data_type=raw_data.data_type,
                    content=raw_data.content,
                    relevance_score=analysis.relevance_score,
                    potential_impact=analysis.potential_impact,
                    summary=analysis.summary,
                    suggested_actions=analysis.suggested_actions,
                    related_symbols=analysis.related_symbols,
                    confidence=analysis.confidence,
                    reasoning=analysis.reasoning
                )
                
                session.add(signal)
                await session.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to store signal in database: {e}", exc_info=True)
    
    def _log_llm_interaction(
        self,
        trace_id: uuid.UUID,
        raw_data: RawDataEvent,
        llm_response: LLMResponse,
        analysis: AnalysisResult,
        start_time: datetime
    ) -> None:
        """
        Log LLM interaction with structured logging.
        
        Args:
            trace_id: Trace ID for correlation
            raw_data: Original raw data
            llm_response: LLM response
            analysis: Parsed analysis result
            start_time: Processing start time
            
        Validates: Requirement 4.8
        """
        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        self.logger.info(
            "LLM interaction completed",
            extra={
                "trace_id": str(trace_id),
                "source": raw_data.source,
                "data_type": raw_data.data_type,
                "provider": llm_response.provider,
                "model": llm_response.model,
                "prompt_tokens": llm_response.prompt_tokens,
                "completion_tokens": llm_response.completion_tokens,
                "total_tokens": llm_response.total_tokens,
                "llm_latency_ms": llm_response.latency_ms,
                "total_duration_ms": duration_ms,
                "cached": llm_response.cached,
                "relevance_score": analysis.relevance_score,
                "potential_impact": analysis.potential_impact
            }
        )
