"""
Execution Engine Module

Orchestrates trading signal generation based on AI analysis and EA configurations.
Subscribes to high-value signals, matches EA profiles, calculates risk, and generates trading signals.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.database.models import EAProfile, User
from system_core.event_bus import EventBus, Event, HighValueSignalEvent, TradingSignalEvent
from system_core.execution_engine.risk_manager import RiskManager

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    Execution Engine orchestrator for trading signal generation.
    
    Responsibilities:
    - Subscribe to Event Bus topic "ai.high_value_signal"
    - Query User Center API for matching EA profiles
    - Calculate position sizes via Risk Manager
    - Generate trading signals
    - Publish signals to Event Bus topic "trading.signal"
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        db_session_factory,
        risk_manager: Optional[RiskManager] = None
    ):
        """
        Initialize Execution Engine.
        
        Args:
            event_bus: Event Bus instance for pub/sub
            db_session_factory: Database session factory for querying EA profiles
            risk_manager: Risk Manager instance (optional, creates default if None)
        """
        self.event_bus = event_bus
        self.db_session_factory = db_session_factory
        self.risk_manager = risk_manager or RiskManager()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        logger.info("ExecutionEngine initialized")
    
    async def start(self):
        """Start the Execution Engine and subscribe to high-value signals."""
        if self._running:
            logger.warning("ExecutionEngine already running")
            return
        
        self._running = True
        
        # Subscribe to high-value signal topic
        await self.event_bus.subscribe(
            "ai.high_value_signal",
            self._handle_high_value_signal
        )
        
        logger.info("ExecutionEngine started, subscribed to 'ai.high_value_signal'")
    
    async def stop(self):
        """Stop the Execution Engine and unsubscribe from topics."""
        if not self._running:
            return
        
        self._running = False
        
        # Unsubscribe from topics
        await self.event_bus.unsubscribe(
            "ai.high_value_signal",
            self._handle_high_value_signal
        )
        
        logger.info("ExecutionEngine stopped")
    
    async def _handle_high_value_signal(self, event: Event):
        """
        Handle incoming high-value signal events.
        
        Args:
            event: High-value signal event from Event Bus
        """
        try:
            # Parse event payload
            signal_data = HighValueSignalEvent(**event.payload)
            
            logger.info(
                f"Received high-value signal: {signal_data.signal_id}, "
                f"relevance_score={signal_data.relevance_score}, "
                f"symbols={signal_data.related_symbols}"
            )
            
            # Query matching EA profiles
            matching_profiles = await self._match_ea_profiles(signal_data)
            
            if not matching_profiles:
                logger.info(
                    f"No matching EA profiles found for signal {signal_data.signal_id}, "
                    f"symbols={signal_data.related_symbols}"
                )
                return
            
            logger.info(
                f"Found {len(matching_profiles)} matching EA profile(s) "
                f"for signal {signal_data.signal_id}"
            )
            
            # Generate trading signals for each matching EA profile
            for ea_profile in matching_profiles:
                await self._generate_trading_signal(signal_data, ea_profile)
        
        except Exception as e:
            logger.error(f"Error handling high-value signal: {e}", exc_info=True)
    
    async def _match_ea_profiles(
        self,
        signal: HighValueSignalEvent
    ) -> list[dict[str, Any]]:
        """
        Query User Center API for matching EA profiles.
        
        Matches EA profiles based on:
        - Signal symbols overlap with EA profile symbols
        - EA profile is enabled/active
        
        Args:
            signal: High-value signal event
        
        Returns:
            List of matching EA profile dictionaries
        """
        try:
            async with self.db_session_factory() as session:
                # Query EA profiles that have overlapping symbols
                stmt = select(EAProfile, User).join(User).where(
                    EAProfile.symbols.overlap(signal.related_symbols)
                )
                
                result = await session.execute(stmt)
                rows = result.all()
                
                matching_profiles = []
                for ea_profile, user in rows:
                    matching_profiles.append({
                        "id": ea_profile.id,
                        "user_id": ea_profile.user_id,
                        "ea_name": ea_profile.ea_name,
                        "symbols": ea_profile.symbols,
                        "timeframe": ea_profile.timeframe,
                        "risk_per_trade": float(ea_profile.risk_per_trade),
                        "max_positions": ea_profile.max_positions,
                        "max_total_risk": float(ea_profile.max_total_risk),
                        "auto_execution": ea_profile.auto_execution,
                        "strategy_logic_description": ea_profile.strategy_logic_description
                    })
                
                return matching_profiles
        
        except Exception as e:
            logger.error(f"Error querying EA profiles: {e}", exc_info=True)
            return []
    
    async def _generate_trading_signal(
        self,
        signal: HighValueSignalEvent,
        ea_profile: dict[str, Any]
    ):
        """
        Generate trading signal based on AI analysis and EA configuration.
        
        Args:
            signal: High-value signal event
            ea_profile: Matching EA profile configuration
        """
        try:
            # Calculate position size via Risk Manager
            position_size = await self.risk_manager.calculate_position_size(
                ea_profile=ea_profile,
                signal=signal.model_dump()
            )
            
            # Determine trading direction based on signal analysis
            # For now, use simple logic based on potential_impact
            # Full implementation will use more sophisticated analysis
            direction = self._determine_direction(signal)
            
            # Generate price levels (placeholder logic)
            # Full implementation will use market data and technical analysis
            entry_price, stop_loss, take_profit = self._calculate_price_levels(
                signal,
                direction
            )
            
            # Create trading signal
            trading_signal = TradingSignalEvent(
                signal_id=uuid4(),
                ea_profile_id=UUID(str(ea_profile["id"])),
                symbol=signal.related_symbols[0] if signal.related_symbols else "UNKNOWN",
                direction=direction,
                volume=float(position_size),
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence_score=signal.confidence,
                reasoning=self._build_reasoning(signal, ea_profile),
                timestamp=datetime.utcnow()
            )
            
            # Log signal generation
            logger.info(
                f"Generated trading signal: {trading_signal.signal_id}, "
                f"EA={ea_profile['ea_name']}, symbol={trading_signal.symbol}, "
                f"direction={trading_signal.direction}, volume={trading_signal.volume}, "
                f"entry={trading_signal.entry_price}, sl={trading_signal.stop_loss}, "
                f"tp={trading_signal.take_profit}, confidence={trading_signal.confidence_score}"
            )
            
            # Publish trading signal to Event Bus
            await self._publish_trading_signal(trading_signal)
        
        except Exception as e:
            logger.error(
                f"Error generating trading signal for EA {ea_profile.get('ea_name')}: {e}",
                exc_info=True
            )
    
    def _determine_direction(self, signal: HighValueSignalEvent) -> str:
        """
        Determine trading direction based on signal analysis.
        
        Placeholder logic:
        - high impact -> long
        - medium impact -> long
        - low impact -> short
        
        Args:
            signal: High-value signal event
        
        Returns:
            Trading direction ("long" or "short")
        """
        if signal.potential_impact in ["high", "medium"]:
            return "long"
        else:
            return "short"
    
    def _calculate_price_levels(
        self,
        signal: HighValueSignalEvent,
        direction: str
    ) -> tuple[float, float, float]:
        """
        Calculate entry, stop loss, and take profit price levels.
        
        Placeholder implementation using simple ratios.
        Full implementation will use market data and technical analysis.
        
        Args:
            signal: High-value signal event
            direction: Trading direction
        
        Returns:
            Tuple of (entry_price, stop_loss, take_profit)
        """
        # Placeholder prices
        # In real implementation, fetch current market price
        base_price = 1.0000
        
        if direction == "long":
            entry_price = base_price
            stop_loss = base_price * 0.99  # 1% below entry
            take_profit = base_price * 1.02  # 2% above entry
        else:  # short
            entry_price = base_price
            stop_loss = base_price * 1.01  # 1% above entry
            take_profit = base_price * 0.98  # 2% below entry
        
        return entry_price, stop_loss, take_profit
    
    def _build_reasoning(
        self,
        signal: HighValueSignalEvent,
        ea_profile: dict[str, Any]
    ) -> str:
        """
        Build reasoning text for trading signal.
        
        Includes AI analysis summary and suggested actions.
        
        Args:
            signal: High-value signal event
            ea_profile: EA profile configuration
        
        Returns:
            Reasoning text
        """
        reasoning_parts = [
            f"AI Analysis Summary: {signal.summary}",
            f"Relevance Score: {signal.relevance_score}/100",
            f"Potential Impact: {signal.potential_impact}",
            f"Confidence: {signal.confidence:.2%}",
        ]
        
        if signal.suggested_actions:
            actions = ", ".join(signal.suggested_actions)
            reasoning_parts.append(f"Suggested Actions: {actions}")
        
        reasoning_parts.append(f"EA Strategy: {ea_profile['ea_name']}")
        
        if signal.reasoning:
            reasoning_parts.append(f"Detailed Analysis: {signal.reasoning}")
        
        return " | ".join(reasoning_parts)
    
    async def _publish_trading_signal(self, trading_signal: TradingSignalEvent):
        """
        Publish trading signal to Event Bus.
        
        Args:
            trading_signal: Trading signal event to publish
        """
        try:
            # Create Event wrapper
            event = Event(
                event_id=uuid4(),
                event_type="trading.signal",
                topic="trading.signal",
                payload=trading_signal.model_dump(),
                timestamp=datetime.utcnow(),
                schema_version="1.0",
                trace_id=uuid4()
            )
            
            # Publish to Event Bus
            await self.event_bus.publish("trading.signal", event.payload)
            
            logger.info(
                f"Published trading signal {trading_signal.signal_id} "
                f"to topic 'trading.signal'"
            )
        
        except Exception as e:
            logger.error(f"Error publishing trading signal: {e}", exc_info=True)
