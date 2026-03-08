"""
Alert Rule Engine

Evaluates high-value signals against user-defined alert rules to determine
which signals should trigger notifications.
"""

from datetime import datetime, time
from typing import Optional, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.config import get_logger
from system_core.database.models import AlertRule

logger = get_logger(__name__)

class AlertRuleEngine:
    """
    Evaluates signals against user alert rules.
    
    Features:
    - Loads user alert rules from database
    - Evaluates rules against incoming high-value signals
    - Filters by relevance score, symbols, impact levels, and time windows
    - Returns whether signal matches at least one rule
    """
    
    def __init__(self, db_session_factory):
        """
        Initialize Alert Rule Engine.
        
        Args:
            db_session_factory: Factory function to create database sessions
        """
        self.db_session_factory = db_session_factory
        logger.info("alert_rule_engine_initialized")
    
    async def evaluate_signal(
        self,
        user_id: UUID,
        signal: dict[str, Any]
    ) -> bool:
        """
        Evaluate if signal matches user's alert rules.
        
        Args:
            user_id: User ID to check rules for
            signal: Signal data dictionary containing:
                - relevance_score: int (0-100)
                - potential_impact: str (low/medium/high)
                - related_symbols: list[str]
                - timestamp: str (ISO 8601 format)
        
        Returns:
            True if signal matches at least one enabled rule, False otherwise
        """
        try:
            # Load user's alert rules
            async with self.db_session_factory() as session:
                rules = await self._load_user_rules(session, user_id)
            
            if not rules:
                # No rules configured - allow all signals by default
                logger.info(
                    "no_alert_rules_configured",
                    user_id=str(user_id),
                    default_action="allow"
                )
                return True
            
            # Evaluate signal against each rule
            for rule in rules:
                if self._matches_rule(signal, rule):
                    logger.info(
                        "signal_matched_alert_rule",
                        user_id=str(user_id),
                        rule_id=str(rule.id),
                        rule_name=rule.rule_name,
                        relevance_score=signal.get('relevance_score')
                    )
                    return True
            
            # No rules matched
            logger.info(
                "signal_filtered_by_alert_rules",
                user_id=str(user_id),
                relevance_score=signal.get('relevance_score'),
                impact=signal.get('potential_impact')
            )
            return False
        
        except Exception as e:
            logger.error(
                "alert_rule_evaluation_error",
                user_id=str(user_id),
                error=str(e)
            )
            # On error, allow signal through (fail-open)
            return True
    
    async def _load_user_rules(
        self,
        session: AsyncSession,
        user_id: UUID
    ) -> list[AlertRule]:
        """
        Load enabled alert rules for user from database.
        
        Args:
            session: Database session
            user_id: User ID
        
        Returns:
            List of enabled AlertRule objects
        """
        result = await session.execute(
            select(AlertRule)
            .where(AlertRule.user_id == user_id)
            .where(AlertRule.enabled == True)
        )
        rules = result.scalars().all()
        
        logger.debug(
            "user_alert_rules_loaded",
            user_id=str(user_id),
            rule_count=len(rules)
        )
        
        return rules
    
    def _matches_rule(
        self,
        signal: dict[str, Any],
        rule: AlertRule
    ) -> bool:
        """
        Check if signal matches a specific alert rule.
        
        Args:
            signal: Signal data dictionary
            rule: AlertRule object
        
        Returns:
            True if signal matches all configured filters in the rule
        """
        # Filter by minimum relevance score
        if rule.min_relevance_score is not None:
            signal_score = signal.get('relevance_score', 0)
            if signal_score < rule.min_relevance_score:
                logger.debug(
                    "signal_filtered_by_relevance_score",
                    rule_id=str(rule.id),
                    signal_score=signal_score,
                    min_score=rule.min_relevance_score
                )
                return False
        
        # Filter by required symbols
        if rule.required_symbols:
            signal_symbols = signal.get('related_symbols', [])
            if not signal_symbols:
                logger.debug(
                    "signal_filtered_no_symbols",
                    rule_id=str(rule.id)
                )
                return False
            
            # Check if any required symbol is in signal symbols
            has_required_symbol = any(
                req_symbol.upper() in [s.upper() for s in signal_symbols]
                for req_symbol in rule.required_symbols
            )
            
            if not has_required_symbol:
                logger.debug(
                    "signal_filtered_by_symbols",
                    rule_id=str(rule.id),
                    required=rule.required_symbols,
                    signal_symbols=signal_symbols
                )
                return False
        
        # Filter by required impact levels
        if rule.required_impact_levels:
            signal_impact = signal.get('potential_impact', '').lower()
            required_impacts = [level.lower() for level in rule.required_impact_levels]
            
            if signal_impact not in required_impacts:
                logger.debug(
                    "signal_filtered_by_impact",
                    rule_id=str(rule.id),
                    signal_impact=signal_impact,
                    required_impacts=required_impacts
                )
                return False
        
        # Filter by time windows
        if rule.time_windows:
            signal_timestamp = signal.get('timestamp')
            if not signal_timestamp:
                # No timestamp - allow through
                pass
            else:
                try:
                    signal_time = datetime.fromisoformat(
                        signal_timestamp.replace('Z', '+00:00')
                    ).time()
                    
                    if not self._is_within_time_windows(signal_time, rule.time_windows):
                        logger.debug(
                            "signal_filtered_by_time_window",
                            rule_id=str(rule.id),
                            signal_time=signal_time.isoformat(),
                            time_windows=rule.time_windows
                        )
                        return False
                except Exception as e:
                    logger.warning(
                        "time_window_parsing_error",
                        rule_id=str(rule.id),
                        timestamp=signal_timestamp,
                        error=str(e)
                    )
                    # On parsing error, allow through
        
        # All filters passed
        return True
    
    def _is_within_time_windows(
        self,
        signal_time: time,
        time_windows: list[str]
    ) -> bool:
        """
        Check if signal time is within any of the configured time windows.
        
        Args:
            signal_time: Signal time object
            time_windows: List of time window strings (e.g., ["09:00-16:00", "20:00-23:00"])
        
        Returns:
            True if signal time is within any time window
        """
        for window in time_windows:
            try:
                # Parse time window (format: "HH:MM-HH:MM")
                start_str, end_str = window.split('-')
                start_time = datetime.strptime(start_str.strip(), '%H:%M').time()
                end_time = datetime.strptime(end_str.strip(), '%H:%M').time()
                
                # Check if signal time is within window
                if start_time <= end_time:
                    # Normal case: 09:00-16:00
                    if start_time <= signal_time <= end_time:
                        return True
                else:
                    # Overnight case: 22:00-02:00
                    if signal_time >= start_time or signal_time <= end_time:
                        return True
            
            except Exception as e:
                logger.warning(
                    "time_window_format_error",
                    window=window,
                    error=str(e)
                )
                continue
        
        return False
