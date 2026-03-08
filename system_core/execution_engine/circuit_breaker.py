"""
Circuit Breaker Module

Safety mechanism that halts auto-execution after detecting consecutive failures.
Tracks execution results per EA profile and triggers on configurable thresholds.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.database.models import CircuitBreakerState, EAProfile

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Circuit Breaker for halting auto-execution on consecutive failures.
    
    Responsibilities:
    - Track execution results per EA profile
    - Trigger on consecutive losses or failures
    - Send urgent notifications when triggered
    - Remain active until manual reset
    - Support configurable thresholds per EA profile
    """
    
    def __init__(self, db_session_factory, push_notification_manager=None):
        """
        Initialize Circuit Breaker.
        
        Args:
            db_session_factory: Database session factory
            push_notification_manager: Push notification manager for alerts
        """
        self.db_session_factory = db_session_factory
        self.push_notification_manager = push_notification_manager
        
        # Default thresholds (can be overridden per EA profile)
        self.default_max_consecutive_losses = 3
        self.default_max_consecutive_failures = 5
        self.default_loss_time_window = 300  # 5 minutes in seconds
        
        logger.info("CircuitBreaker initialized")
    
    async def check_should_halt(self, ea_profile_id: UUID) -> tuple[bool, Optional[str]]:
        """
        Check if circuit breaker is active for EA profile.
        
        Args:
            ea_profile_id: EA profile ID
        
        Returns:
            Tuple of (should_halt, reason)
        """
        try:
            async with self.db_session_factory() as session:
                # Query circuit breaker state
                stmt = select(CircuitBreakerState).where(
                    CircuitBreakerState.ea_profile_id == ea_profile_id
                )
                result = await session.execute(stmt)
                cb_state = result.scalar_one_or_none()
                
                if cb_state and cb_state.is_active:
                    reason = (
                        f"Circuit breaker is active for EA profile {ea_profile_id}. "
                        f"Reason: {cb_state.trigger_reason}. "
                        f"Triggered at: {cb_state.triggered_at}. "
                        f"Manual reset required via POST /api/ea-profiles/{ea_profile_id}/reset-circuit-breaker"
                    )
                    logger.warning(reason)
                    return True, reason
                
                return False, None
        
        except Exception as e:
            logger.error(f"Error checking circuit breaker state: {e}", exc_info=True)
            # On error, halt to be safe
            return True, f"Error checking circuit breaker: {str(e)}"
    
    async def record_trade_loss(
        self,
        ea_profile_id: UUID,
        trade_id: UUID,
        pnl: Decimal,
        execution_time: datetime
    ):
        """
        Record a trade loss and check if circuit breaker should trigger.
        
        Triggers if >3 consecutive trades result in immediate losses (within 5 minutes).
        
        Args:
            ea_profile_id: EA profile ID
            trade_id: Trade ID
            pnl: Profit/loss amount (negative for loss)
            execution_time: Trade execution time
        """
        try:
            async with self.db_session_factory() as session:
                # Get or create circuit breaker state
                cb_state = await self._get_or_create_state(session, ea_profile_id)
                
                # Get time window from EA profile
                time_window = await self._get_loss_time_window(session, ea_profile_id)
                
                # Check if this is an immediate loss (within time window)
                time_since_execution = (datetime.utcnow() - execution_time).total_seconds()
                
                if pnl < 0 and time_since_execution <= time_window:
                    # Increment consecutive losses
                    cb_state.consecutive_losses += 1
                    logger.info(
                        f"Recorded immediate loss for EA {ea_profile_id}: "
                        f"consecutive_losses={cb_state.consecutive_losses}, "
                        f"pnl={pnl}, time_since_execution={time_since_execution}s, "
                        f"time_window={time_window}s"
                    )
                else:
                    # Reset consecutive losses if not immediate loss
                    if cb_state.consecutive_losses > 0:
                        logger.info(
                            f"Resetting consecutive losses for EA {ea_profile_id} "
                            f"(previous: {cb_state.consecutive_losses})"
                        )
                    cb_state.consecutive_losses = 0
                
                # Get threshold from EA profile or use default
                max_losses = await self._get_max_consecutive_losses(session, ea_profile_id)
                
                # Check if threshold exceeded
                if cb_state.consecutive_losses > max_losses:
                    await self._trigger_circuit_breaker(
                        session,
                        cb_state,
                        ea_profile_id,
                        f"More than {max_losses} consecutive trades with immediate losses "
                        f"(within {time_window}s)"
                    )
                
                cb_state.updated_at = datetime.utcnow()
                await session.commit()
        
        except Exception as e:
            logger.error(f"Error recording trade loss: {e}", exc_info=True)
    
    async def record_order_failure(
        self,
        ea_profile_id: UUID,
        error_message: str
    ):
        """
        Record an order submission failure and check if circuit breaker should trigger.
        
        Triggers if >5 consecutive order submissions fail.
        
        Args:
            ea_profile_id: EA profile ID
            error_message: Error message from broker
        """
        try:
            async with self.db_session_factory() as session:
                # Get or create circuit breaker state
                cb_state = await self._get_or_create_state(session, ea_profile_id)
                
                # Increment consecutive failures
                cb_state.consecutive_failures += 1
                logger.info(
                    f"Recorded order failure for EA {ea_profile_id}: "
                    f"consecutive_failures={cb_state.consecutive_failures}, "
                    f"error={error_message}"
                )
                
                # Get threshold from EA profile or use default
                max_failures = await self._get_max_consecutive_failures(session, ea_profile_id)
                
                # Check if threshold exceeded
                if cb_state.consecutive_failures > max_failures:
                    await self._trigger_circuit_breaker(
                        session,
                        cb_state,
                        ea_profile_id,
                        f"More than {max_failures} consecutive order submission failures"
                    )
                
                cb_state.updated_at = datetime.utcnow()
                await session.commit()
        
        except Exception as e:
            logger.error(f"Error recording order failure: {e}", exc_info=True)
    
    async def record_order_success(self, ea_profile_id: UUID):
        """
        Record a successful order submission.
        
        Resets consecutive_failures counter.
        
        Args:
            ea_profile_id: EA profile ID
        """
        try:
            async with self.db_session_factory() as session:
                # Get or create circuit breaker state
                cb_state = await self._get_or_create_state(session, ea_profile_id)
                
                # Reset consecutive failures
                if cb_state.consecutive_failures > 0:
                    logger.info(
                        f"Resetting consecutive failures for EA {ea_profile_id} "
                        f"(previous: {cb_state.consecutive_failures})"
                    )
                    cb_state.consecutive_failures = 0
                    cb_state.updated_at = datetime.utcnow()
                    await session.commit()
        
        except Exception as e:
            logger.error(f"Error recording order success: {e}", exc_info=True)
    
    async def reset(self, ea_profile_id: UUID, user_id: Optional[UUID] = None) -> bool:
        """
        Manually reset circuit breaker for EA profile.
        
        Args:
            ea_profile_id: EA profile ID
            user_id: User ID performing reset (for audit)
        
        Returns:
            True if reset successful, False otherwise
        """
        try:
            async with self.db_session_factory() as session:
                # Query circuit breaker state
                stmt = select(CircuitBreakerState).where(
                    CircuitBreakerState.ea_profile_id == ea_profile_id
                )
                result = await session.execute(stmt)
                cb_state = result.scalar_one_or_none()
                
                if not cb_state:
                    logger.warning(f"No circuit breaker state found for EA {ea_profile_id}")
                    return False
                
                # Reset state
                was_active = cb_state.is_active
                cb_state.is_active = False
                cb_state.consecutive_losses = 0
                cb_state.consecutive_failures = 0
                cb_state.reset_at = datetime.utcnow()
                cb_state.updated_at = datetime.utcnow()
                
                await session.commit()
                
                if was_active:
                    logger.info(
                        f"Circuit breaker reset for EA {ea_profile_id} by user {user_id}"
                    )
                    
                    # Send notification about reset
                    if self.push_notification_manager:
                        await self._send_reset_notification(ea_profile_id, user_id)
                
                return True
        
        except Exception as e:
            logger.error(f"Error resetting circuit breaker: {e}", exc_info=True)
            return False
    
    async def get_status(self, ea_profile_id: UUID) -> dict[str, Any]:
        """
        Get circuit breaker status for EA profile.
        
        Args:
            ea_profile_id: EA profile ID
        
        Returns:
            Dictionary with circuit breaker status
        """
        try:
            async with self.db_session_factory() as session:
                stmt = select(CircuitBreakerState).where(
                    CircuitBreakerState.ea_profile_id == ea_profile_id
                )
                result = await session.execute(stmt)
                cb_state = result.scalar_one_or_none()
                
                if not cb_state:
                    return {
                        "is_active": False,
                        "consecutive_losses": 0,
                        "consecutive_failures": 0,
                        "triggered_at": None,
                        "trigger_reason": None
                    }
                
                return {
                    "is_active": cb_state.is_active,
                    "consecutive_losses": cb_state.consecutive_losses,
                    "consecutive_failures": cb_state.consecutive_failures,
                    "triggered_at": cb_state.triggered_at.isoformat() if cb_state.triggered_at else None,
                    "trigger_reason": cb_state.trigger_reason,
                    "reset_at": cb_state.reset_at.isoformat() if cb_state.reset_at else None
                }
        
        except Exception as e:
            logger.error(f"Error getting circuit breaker status: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _get_or_create_state(
        self,
        session: AsyncSession,
        ea_profile_id: UUID
    ) -> CircuitBreakerState:
        """Get or create circuit breaker state for EA profile."""
        stmt = select(CircuitBreakerState).where(
            CircuitBreakerState.ea_profile_id == ea_profile_id
        )
        result = await session.execute(stmt)
        cb_state = result.scalar_one_or_none()
        
        if not cb_state:
            cb_state = CircuitBreakerState(
                ea_profile_id=ea_profile_id,
                consecutive_losses=0,
                consecutive_failures=0,
                is_active=False
            )
            session.add(cb_state)
            await session.flush()
        
        return cb_state
    
    async def _get_max_consecutive_losses(
        self,
        session: AsyncSession,
        ea_profile_id: UUID
    ) -> int:
        """Get max consecutive losses threshold from EA profile or use default."""
        try:
            stmt = select(EAProfile).where(EAProfile.id == ea_profile_id)
            result = await session.execute(stmt)
            ea_profile = result.scalar_one_or_none()
            
            if ea_profile and ea_profile.max_consecutive_losses is not None:
                return ea_profile.max_consecutive_losses
            
            return self.default_max_consecutive_losses
        except Exception as e:
            logger.error(f"Error getting max consecutive losses: {e}", exc_info=True)
            return self.default_max_consecutive_losses
    
    async def _get_max_consecutive_failures(
        self,
        session: AsyncSession,
        ea_profile_id: UUID
    ) -> int:
        """Get max consecutive failures threshold from EA profile or use default."""
        try:
            stmt = select(EAProfile).where(EAProfile.id == ea_profile_id)
            result = await session.execute(stmt)
            ea_profile = result.scalar_one_or_none()
            
            if ea_profile and ea_profile.max_consecutive_failures is not None:
                return ea_profile.max_consecutive_failures
            
            return self.default_max_consecutive_failures
        except Exception as e:
            logger.error(f"Error getting max consecutive failures: {e}", exc_info=True)
            return self.default_max_consecutive_failures
    
    async def _get_loss_time_window(
        self,
        session: AsyncSession,
        ea_profile_id: UUID
    ) -> int:
        """Get loss time window from EA profile or use default."""
        try:
            stmt = select(EAProfile).where(EAProfile.id == ea_profile_id)
            result = await session.execute(stmt)
            ea_profile = result.scalar_one_or_none()
            
            if ea_profile and ea_profile.loss_time_window_seconds is not None:
                return ea_profile.loss_time_window_seconds
            
            return self.default_loss_time_window
        except Exception as e:
            logger.error(f"Error getting loss time window: {e}", exc_info=True)
            return self.default_loss_time_window
    
    async def _trigger_circuit_breaker(
        self,
        session: AsyncSession,
        cb_state: CircuitBreakerState,
        ea_profile_id: UUID,
        reason: str
    ):
        """Trigger circuit breaker and send urgent notification."""
        if cb_state.is_active:
            # Already active, don't trigger again
            return
        
        cb_state.is_active = True
        cb_state.triggered_at = datetime.utcnow()
        cb_state.trigger_reason = reason
        
        logger.critical(
            f"CIRCUIT BREAKER TRIGGERED for EA {ea_profile_id}: {reason}"
        )
        
        # Send urgent notification via all enabled channels
        if self.push_notification_manager:
            await self._send_trigger_notification(ea_profile_id, reason)
    
    async def _send_trigger_notification(self, ea_profile_id: UUID, reason: str):
        """Send urgent notification when circuit breaker triggers."""
        try:
            # Get EA profile info
            async with self.db_session_factory() as session:
                stmt = select(EAProfile).where(EAProfile.id == ea_profile_id)
                result = await session.execute(stmt)
                ea_profile = result.scalar_one_or_none()
                
                if not ea_profile:
                    logger.error(f"EA profile {ea_profile_id} not found")
                    return
                
                message = (
                    f"🚨 URGENT: Circuit Breaker Triggered 🚨\n\n"
                    f"EA: {ea_profile.ea_name}\n"
                    f"Reason: {reason}\n"
                    f"Time: {datetime.utcnow().isoformat()}\n\n"
                    f"Auto-execution has been halted for this EA profile.\n"
                    f"Manual reset required via:\n"
                    f"POST /api/ea-profiles/{ea_profile_id}/reset-circuit-breaker"
                )
                
                # Send via push notification manager
                # This will send to all enabled channels for the user
                await self.push_notification_manager.send_notification(
                    user_id=ea_profile.user_id,
                    message=message,
                    priority="urgent"
                )
                
                logger.info(f"Sent circuit breaker trigger notification for EA {ea_profile_id}")
        
        except Exception as e:
            logger.error(f"Error sending trigger notification: {e}", exc_info=True)
    
    async def _send_reset_notification(self, ea_profile_id: UUID, user_id: Optional[UUID]):
        """Send notification when circuit breaker is reset."""
        try:
            async with self.db_session_factory() as session:
                stmt = select(EAProfile).where(EAProfile.id == ea_profile_id)
                result = await session.execute(stmt)
                ea_profile = result.scalar_one_or_none()
                
                if not ea_profile:
                    return
                
                message = (
                    f"✅ Circuit Breaker Reset\n\n"
                    f"EA: {ea_profile.ea_name}\n"
                    f"Reset by: User {user_id}\n"
                    f"Time: {datetime.utcnow().isoformat()}\n\n"
                    f"Auto-execution has been re-enabled for this EA profile."
                )
                
                await self.push_notification_manager.send_notification(
                    user_id=ea_profile.user_id,
                    message=message,
                    priority="normal"
                )
                
                logger.info(f"Sent circuit breaker reset notification for EA {ea_profile_id}")
        
        except Exception as e:
            logger.error(f"Error sending reset notification: {e}", exc_info=True)
