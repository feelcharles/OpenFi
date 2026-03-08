"""
Risk Manager Module

Calculates position sizes and enforces risk limits for trading signals.
Implements multiple position sizing methods and adaptive risk scaling.
"""

from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
import logging
import math

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Risk Manager for position sizing and risk limit enforcement.
    
    Responsibilities:
    - Calculate position sizes using multiple methods
    - Enforce max_positions and total_risk_limit
    - Track recent performance for adaptive risk scaling
    - Validate trades against risk limits
    """
    
    def __init__(self, db_session_factory=None):
        """
        Initialize Risk Manager.
        
        Args:
            db_session_factory: Database session factory for querying positions
        """
        self.db_session_factory = db_session_factory
        # Track recent performance per EA profile for adaptive scaling
        self._performance_tracker: dict[UUID, list[dict[str, Any]]] = {}
        logger.info("RiskManager initialized")
    
    async def calculate_position_size(
        self,
        ea_profile: dict[str, Any],
        signal: dict[str, Any],
        account_balance: Decimal = Decimal("10000.00"),
        entry_price: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        method: Optional[str] = None
    ) -> Decimal:
        """
        Calculate position size based on risk parameters and selected method.
        
        Formula (fixed_percentage):
        position_size = (account_balance * risk_per_trade) / (entry_price - stop_loss)
        
        Args:
            ea_profile: EA profile configuration
            signal: High-value signal data
            account_balance: Current account balance (default: 10000)
            entry_price: Entry price for the trade (optional, extracted from signal if not provided)
            stop_loss: Stop loss price (optional, extracted from signal if not provided)
            method: Position sizing method (fixed_percentage, fixed_amount, kelly_criterion, volatility_based)
        
        Returns:
            Calculated position size
        """
        try:
            # Extract risk parameters
            risk_per_trade = Decimal(str(ea_profile.get("risk_per_trade", 0.01)))
            ea_profile_id = ea_profile.get("id")
            
            # Determine position sizing method
            sizing_method = method or ea_profile.get("position_sizing_method", "fixed_percentage")
            
            # Extract prices if not provided
            if entry_price is None:
                entry_price = Decimal(str(signal.get("entry_price", "1.0")))
            if stop_loss is None:
                stop_loss = Decimal(str(signal.get("stop_loss", "0.99")))
            
            # Calculate base position size using selected method
            if sizing_method == "fixed_percentage":
                position_size = self._calculate_fixed_percentage(
                    account_balance, risk_per_trade, entry_price, stop_loss
                )
            elif sizing_method == "fixed_amount":
                position_size = self._calculate_fixed_amount(
                    ea_profile, entry_price, stop_loss
                )
            elif sizing_method == "kelly_criterion":
                position_size = self._calculate_kelly_criterion(
                    account_balance, risk_per_trade, entry_price, stop_loss, ea_profile_id
                )
            elif sizing_method == "volatility_based":
                position_size = self._calculate_volatility_based(
                    account_balance, risk_per_trade, entry_price, stop_loss, signal
                )
            else:
                logger.warning(f"Unknown sizing method '{sizing_method}', using fixed_percentage")
                position_size = self._calculate_fixed_percentage(
                    account_balance, risk_per_trade, entry_price, stop_loss
                )
            
            # Apply adaptive risk scaling based on recent performance
            if ea_profile_id:
                position_size = self._apply_adaptive_scaling(ea_profile_id, position_size)
            
            logger.info(
                f"Calculated position size: {position_size} "
                f"(method={sizing_method}, risk_per_trade={risk_per_trade}, "
                f"account_balance={account_balance}, entry={entry_price}, sl={stop_loss})"
            )
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}", exc_info=True)
            # Return minimum position size on error
            return Decimal("0.01")
    
    def _calculate_fixed_percentage(
        self,
        account_balance: Decimal,
        risk_per_trade: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal
    ) -> Decimal:
        """
        Calculate position size using fixed percentage method.
        
        Formula: (account_balance * risk_per_trade) / abs(entry_price - stop_loss)
        
        Args:
            account_balance: Current account balance
            risk_per_trade: Risk percentage per trade (e.g., 0.02 for 2%)
            entry_price: Entry price
            stop_loss: Stop loss price
        
        Returns:
            Position size
        """
        risk_amount = account_balance * risk_per_trade
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            logger.warning("Price risk is zero, using minimum position size")
            return Decimal("0.01")
        
        position_size = risk_amount / price_risk
        return max(position_size, Decimal("0.01"))
    
    def _calculate_fixed_amount(
        self,
        ea_profile: dict[str, Any],
        entry_price: Decimal,
        stop_loss: Decimal
    ) -> Decimal:
        """
        Calculate position size using fixed amount method.
        
        Uses a fixed dollar amount to risk per trade.
        
        Args:
            ea_profile: EA profile configuration
            entry_price: Entry price
            stop_loss: Stop loss price
        
        Returns:
            Position size
        """
        fixed_risk_amount = Decimal(str(ea_profile.get("fixed_risk_amount", "100.00")))
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            logger.warning("Price risk is zero, using minimum position size")
            return Decimal("0.01")
        
        position_size = fixed_risk_amount / price_risk
        return max(position_size, Decimal("0.01"))
    
    def _calculate_kelly_criterion(
        self,
        account_balance: Decimal,
        risk_per_trade: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        ea_profile_id: Optional[UUID]
    ) -> Decimal:
        """
        Calculate position size using Kelly Criterion.
        
        Kelly % = (Win Rate * Avg Win - Loss Rate * Avg Loss) / Avg Win
        
        Args:
            account_balance: Current account balance
            risk_per_trade: Base risk percentage
            entry_price: Entry price
            stop_loss: Stop loss price
            ea_profile_id: EA profile ID for performance tracking
        
        Returns:
            Position size
        """
        # Get recent performance stats
        win_rate, avg_win, avg_loss = self._get_performance_stats(ea_profile_id)
        
        if win_rate == 0 or avg_win == 0:
            # Not enough data, fall back to fixed percentage
            return self._calculate_fixed_percentage(
                account_balance, risk_per_trade, entry_price, stop_loss
            )
        
        # Calculate Kelly percentage
        loss_rate = Decimal("1.0") - win_rate
        kelly_pct = (win_rate * avg_win - loss_rate * avg_loss) / avg_win
        
        # Apply fractional Kelly (use 25% of full Kelly to be conservative)
        kelly_pct = kelly_pct * Decimal("0.25")
        
        # Cap at risk_per_trade to avoid over-leveraging
        kelly_pct = min(kelly_pct, risk_per_trade)
        kelly_pct = max(kelly_pct, Decimal("0.001"))  # Minimum 0.1%
        
        # Calculate position size
        risk_amount = account_balance * kelly_pct
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            return Decimal("0.01")
        
        position_size = risk_amount / price_risk
        return max(position_size, Decimal("0.01"))
    
    def _calculate_volatility_based(
        self,
        account_balance: Decimal,
        risk_per_trade: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        signal: dict[str, Any]
    ) -> Decimal:
        """
        Calculate position size based on market volatility.
        
        Adjusts position size inversely to volatility - higher volatility = smaller position.
        
        Args:
            account_balance: Current account balance
            risk_per_trade: Base risk percentage
            entry_price: Entry price
            stop_loss: Stop loss price
            signal: Signal data (may contain volatility info)
        
        Returns:
            Position size
        """
        # Extract volatility from signal metadata if available
        volatility = Decimal(str(signal.get("volatility", "0.01")))
        
        # Normalize volatility (assume 1% is normal, adjust risk accordingly)
        normal_volatility = Decimal("0.01")
        volatility_adjustment = normal_volatility / max(volatility, Decimal("0.001"))
        
        # Cap adjustment between 0.5x and 2x
        volatility_adjustment = max(min(volatility_adjustment, Decimal("2.0")), Decimal("0.5"))
        
        # Calculate base position size
        base_position = self._calculate_fixed_percentage(
            account_balance, risk_per_trade, entry_price, stop_loss
        )
        
        # Apply volatility adjustment
        position_size = base_position * volatility_adjustment
        return max(position_size, Decimal("0.01"))
    
    def _apply_adaptive_scaling(
        self,
        ea_profile_id: UUID,
        position_size: Decimal
    ) -> Decimal:
        """
        Apply adaptive risk scaling based on recent performance.
        
        Reduces position size after consecutive losses.
        
        Args:
            ea_profile_id: EA profile ID
            position_size: Base position size
        
        Returns:
            Adjusted position size
        """
        if ea_profile_id not in self._performance_tracker:
            return position_size
        
        recent_trades = self._performance_tracker[ea_profile_id]
        
        if not recent_trades:
            return position_size
        
        # Count consecutive losses
        consecutive_losses = 0
        for trade in reversed(recent_trades):
            if trade.get("pnl", 0) < 0:
                consecutive_losses += 1
            else:
                break
        
        # Apply scaling based on consecutive losses
        if consecutive_losses == 0:
            scaling_factor = Decimal("1.0")
        elif consecutive_losses == 1:
            scaling_factor = Decimal("0.9")  # 10% reduction
        elif consecutive_losses == 2:
            scaling_factor = Decimal("0.75")  # 25% reduction
        elif consecutive_losses == 3:
            scaling_factor = Decimal("0.5")  # 50% reduction
        else:
            scaling_factor = Decimal("0.25")  # 75% reduction
        
        adjusted_size = position_size * scaling_factor
        
        if scaling_factor < Decimal("1.0"):
            logger.info(
                f"Applied adaptive scaling: {consecutive_losses} consecutive losses, "
                f"scaling factor={scaling_factor}, "
                f"original={position_size}, adjusted={adjusted_size}"
            )
        
        return max(adjusted_size, Decimal("0.01"))
    
    def _get_performance_stats(
        self,
        ea_profile_id: Optional[UUID]
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Get performance statistics for Kelly Criterion calculation.
        
        Args:
            ea_profile_id: EA profile ID
        
        Returns:
            Tuple of (win_rate, avg_win, avg_loss)
        """
        if not ea_profile_id or ea_profile_id not in self._performance_tracker:
            return Decimal("0.5"), Decimal("1.0"), Decimal("1.0")
        
        recent_trades = self._performance_tracker[ea_profile_id]
        
        if not recent_trades:
            return Decimal("0.5"), Decimal("1.0"), Decimal("1.0")
        
        wins = [t for t in recent_trades if t.get("pnl", 0) > 0]
        losses = [t for t in recent_trades if t.get("pnl", 0) < 0]
        
        total_trades = len(recent_trades)
        win_count = len(wins)
        
        win_rate = Decimal(str(win_count / total_trades)) if total_trades > 0 else Decimal("0.5")
        
        avg_win = Decimal(str(sum(t["pnl"] for t in wins) / len(wins))) if wins else Decimal("1.0")
        avg_loss = abs(Decimal(str(sum(t["pnl"] for t in losses) / len(losses)))) if losses else Decimal("1.0")
        
        return win_rate, avg_win, avg_loss
    
    def record_trade_result(
        self,
        ea_profile_id: UUID,
        pnl: Decimal,
        timestamp: Optional[datetime] = None
    ):
        """
        Record trade result for adaptive risk scaling.
        
        Args:
            ea_profile_id: EA profile ID
            pnl: Profit/loss amount
            timestamp: Trade timestamp (default: now)
        """
        if ea_profile_id not in self._performance_tracker:
            self._performance_tracker[ea_profile_id] = []
        
        trade_record = {
            "pnl": float(pnl),
            "timestamp": timestamp or datetime.utcnow()
        }
        
        self._performance_tracker[ea_profile_id].append(trade_record)
        
        # Keep only last 20 trades for performance tracking
        if len(self._performance_tracker[ea_profile_id]) > 20:
            self._performance_tracker[ea_profile_id] = self._performance_tracker[ea_profile_id][-20:]
    
    async def check_risk_limits(
        self,
        ea_profile: dict[str, Any],
        new_position_size: Decimal,
        account_balance: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that new trade doesn't exceed risk limits.
        
        Checks:
        1. Max positions limit
        2. Total risk exposure limit
        
        Args:
            ea_profile: EA profile configuration
            new_position_size: Proposed position size
            account_balance: Current account balance
            entry_price: Entry price
            stop_loss: Stop loss price
        
        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        try:
            ea_profile_id = ea_profile.get("id")
            user_id = ea_profile.get("user_id")
            max_positions = ea_profile.get("max_positions", 1)
            total_risk_limit = Decimal(str(ea_profile.get("max_total_risk", 0.10)))
            
            # Check if we have database access
            if not self.db_session_factory:
                logger.warning("No database session factory, skipping risk limit checks")
                return True, None
            
            # Query current open positions
            async with self.db_session_factory() as session:
                from system_core.database.models import Trade
                
                # Count open positions for this EA profile
                stmt = select(Trade).where(
                    and_(
                        Trade.ea_profile_id == ea_profile_id,
                        Trade.status.in_(["open", "pending"])
                    )
                )
                result = await session.execute(stmt)
                open_positions = result.scalars().all()
                
                # Check max positions limit
                if len(open_positions) >= max_positions:
                    rejection_reason = (
                        f"Max positions limit exceeded: {len(open_positions)}/{max_positions} "
                        f"positions already open for EA '{ea_profile.get('ea_name')}'"
                    )
                    logger.warning(rejection_reason)
                    return False, rejection_reason
                
                # Calculate current risk exposure
                current_risk = Decimal("0")
                for position in open_positions:
                    position_risk = abs(position.entry_price - position.stop_loss) * position.volume
                    current_risk += position_risk
                
                # Calculate new position risk
                new_position_risk = abs(entry_price - stop_loss) * new_position_size
                
                # Calculate total risk as percentage of account balance
                total_risk = (current_risk + new_position_risk) / account_balance
                
                # Check total risk limit
                if total_risk > total_risk_limit:
                    rejection_reason = (
                        f"Total risk limit exceeded: {total_risk:.2%} > {total_risk_limit:.2%} "
                        f"(current risk: {current_risk}, new position risk: {new_position_risk}, "
                        f"account balance: {account_balance})"
                    )
                    logger.warning(rejection_reason)
                    return False, rejection_reason
                
                logger.info(
                    f"Risk limits check passed: {len(open_positions)}/{max_positions} positions, "
                    f"total risk: {total_risk:.2%}/{total_risk_limit:.2%}"
                )
                
                return True, None
        
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}", exc_info=True)
            # On error, reject to be safe
            return False, f"Error checking risk limits: {str(e)}"
    
    async def get_current_exposure(
        self,
        user_id: UUID
    ) -> dict[str, Any]:
        """
        Get current risk exposure for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Dictionary with exposure metrics
        """
        try:
            if not self.db_session_factory:
                return {
                    "total_positions": 0,
                    "total_risk": Decimal("0"),
                    "positions_by_ea": {}
                }
            
            async with self.db_session_factory() as session:
                from system_core.database.models import Trade
                
                # Query all open positions for user
                stmt = select(Trade).where(
                    and_(
                        Trade.user_id == user_id,
                        Trade.status.in_(["open", "pending"])
                    )
                )
                result = await session.execute(stmt)
                open_positions = result.scalars().all()
                
                # Calculate exposure metrics
                total_risk = Decimal("0")
                positions_by_ea = {}
                
                for position in open_positions:
                    position_risk = abs(position.entry_price - position.stop_loss) * position.volume
                    total_risk += position_risk
                    
                    ea_id = str(position.ea_profile_id)
                    if ea_id not in positions_by_ea:
                        positions_by_ea[ea_id] = {
                            "count": 0,
                            "risk": Decimal("0")
                        }
                    
                    positions_by_ea[ea_id]["count"] += 1
                    positions_by_ea[ea_id]["risk"] += position_risk
                
                return {
                    "total_positions": len(open_positions),
                    "total_risk": total_risk,
                    "positions_by_ea": positions_by_ea
                }
        
        except Exception as e:
            logger.error(f"Error getting current exposure: {e}", exc_info=True)
            return {
                "total_positions": 0,
                "total_risk": Decimal("0"),
                "positions_by_ea": {},
                "error": str(e)
            }
