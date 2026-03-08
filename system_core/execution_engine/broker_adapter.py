"""
Broker Adapter Module

Provides abstract interface for connecting to trading platform APIs.
Implements placeholder/stub adapters for MT4, MT5, and other brokers.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class Order(BaseModel):
    """Order specification for broker submission."""
    
    symbol: str
    direction: str  # long, short
    volume: Decimal
    order_type: str  # market, limit, stop
    entry_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    magic_number: Optional[int] = None

class OrderResult(BaseModel):
    """Order submission result from broker."""
    
    success: bool
    order_id: Optional[str] = None
    execution_price: Optional[Decimal] = None
    error_message: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

class Position(BaseModel):
    """Open position from broker."""
    
    position_id: str
    symbol: str
    direction: str
    volume: Decimal
    entry_price: Decimal
    current_price: Decimal
    pnl: Decimal
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None

class AccountInfo(BaseModel):
    """Account information from broker."""
    
    account_number: str
    balance: Decimal
    equity: Decimal
    margin_used: Decimal
    margin_free: Decimal
    currency: str = "USD"

class BrokerAdapter(ABC):
    """
    Abstract broker adapter interface.
    
    Defines standard methods for broker integration:
    - connect/disconnect
    - submit_order/cancel_order
    - get_positions/get_account_info
    """
    
    def __init__(self, config: dict[str, Any]):
        """
        Initialize broker adapter.
        
        Args:
            config: Broker connection configuration
        """
        self.config = config
        self.connected = False
        logger.info(f"{self.__class__.__name__} initialized")
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to broker API.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Close connection to broker API.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def submit_order(self, order: Order) -> OrderResult:
        """
        Submit order to broker.
        
        Args:
            order: Order specification
        
        Returns:
            Order submission result
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel pending order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancellation successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """
        Get current open positions.
        
        Returns:
            List of open positions
        """
        pass
    
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """
        Get account information.
        
        Returns:
            Account information
        """
        pass

class MT4Adapter(BrokerAdapter):
    """
    MT4 broker adapter (placeholder/stub implementation).
    
    Full implementation will integrate with MT4 API.
    Includes connection management, error handling, and broker-specific error code translation.
    """
    
    def __init__(self, config: dict[str, Any]):
        """
        Initialize MT4 adapter.
        
        Args:
            config: Broker connection configuration with keys:
                - server: MT4 server address
                - account_number: Trading account number
                - password: Account password
                - timeout: Connection timeout in seconds (default: 30)
        """
        super().__init__(config)
        self.server = config.get("server")
        self.account_number = config.get("account_number")
        self.password = config.get("password")
        self.timeout = config.get("timeout", 30)
        self.connection_attempts = 0
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 1  # Initial delay in seconds
    
    async def connect(self) -> bool:
        """
        Establish connection to MT4 broker.
        
        Implements automatic reconnection with exponential backoff.
        """
        try:
            logger.info(
                f"MT4Adapter: Connecting to broker - "
                f"server={self.server}, account={self.account_number}"
            )
            
            # Placeholder: simulate connection with validation
            if not self.server or not self.account_number:
                logger.error("MT4Adapter: Missing required connection parameters")
                return False
            
            await asyncio.sleep(0.1)
            
            # Verify authentication (placeholder)
            if not await self._verify_authentication():
                logger.error("MT4Adapter: Authentication failed")
                return False
            
            self.connected = True
            self.connection_attempts = 0
            logger.info("MT4Adapter: Connected successfully")
            return True
        
        except Exception as e:
            logger.error(f"MT4Adapter: Connection failed: {e}")
            self.connected = False
            
            # Attempt reconnection with exponential backoff
            if self.connection_attempts < self.max_reconnect_attempts:
                self.connection_attempts += 1
                delay = self.reconnect_delay * (2 ** (self.connection_attempts - 1))
                logger.info(
                    f"MT4Adapter: Reconnecting in {delay}s "
                    f"(attempt {self.connection_attempts}/{self.max_reconnect_attempts})"
                )
                await asyncio.sleep(delay)
                return await self.connect()
            
            logger.error("MT4Adapter: Max reconnection attempts reached")
            return False
    
    async def _verify_authentication(self) -> bool:
        """Verify authentication with broker (placeholder)."""
        # Placeholder: simulate authentication check
        await asyncio.sleep(0.05)
        return True
    
    async def disconnect(self) -> bool:
        """Close connection to MT4 broker."""
        try:
            logger.info("MT4Adapter: Disconnecting from broker...")
            self.connected = False
            logger.info("MT4Adapter: Disconnected successfully")
            return True
        except Exception as e:
            logger.error(f"MT4Adapter: Disconnection failed: {e}")
            return False
    
    async def submit_order(self, order: Order) -> OrderResult:
        """
        Submit order to MT4 broker (placeholder).
        
        Translates internal order format to MT4-specific format.
        Handles MT4-specific error codes.
        """
        try:
            if not self.connected:
                # Attempt to reconnect
                if not await self.connect():
                    return OrderResult(
                        success=False,
                        error_message="Not connected to broker and reconnection failed"
                    )
            
            logger.info(
                f"MT4Adapter: Submitting order - {order.symbol} {order.direction} "
                f"{order.volume} @ {order.order_type}"
            )
            
            # Validate order parameters
            validation_error = self._validate_order(order)
            if validation_error:
                return OrderResult(
                    success=False,
                    error_message=validation_error
                )
            
            # Translate to MT4 order format
            mt4_order = self._translate_to_mt4_format(order)
            
            # Placeholder: simulate order submission
            await asyncio.sleep(0.1)
            
            # Simulate potential MT4 errors (for testing)
            # In real implementation, this would be actual broker response
            error_code = None  # 0 = success
            
            if error_code:
                error_message = self._translate_mt4_error(error_code)
                logger.error(f"MT4Adapter: Order submission failed - {error_message}")
                return OrderResult(
                    success=False,
                    error_message=error_message
                )
            
            # Generate mock order ID
            order_id = f"MT4-{uuid4().hex[:8]}"
            
            # Use entry price or simulate execution price
            execution_price = order.entry_price or Decimal("1.0000")
            
            logger.info(
                f"MT4Adapter: Order submitted successfully - "
                f"order_id={order_id}, execution_price={execution_price}"
            )
            
            return OrderResult(
                success=True,
                order_id=order_id,
                execution_price=execution_price,
                timestamp=datetime.utcnow()
            )
        
        except Exception as e:
            logger.error(f"MT4Adapter: Order submission failed: {e}")
            return OrderResult(
                success=False,
                error_message=f"Exception during order submission: {str(e)}"
            )
    
    def _validate_order(self, order: Order) -> Optional[str]:
        """
        Validate order parameters.
        
        Returns:
            Error message if validation fails, None if valid
        """
        if not order.symbol:
            return "Symbol is required"
        
        if order.volume <= 0:
            return "Volume must be positive"
        
        if order.direction not in ["long", "short"]:
            return f"Invalid direction: {order.direction}"
        
        if order.order_type not in ["market", "limit", "stop"]:
            return f"Invalid order type: {order.order_type}"
        
        return None
    
    def _translate_to_mt4_format(self, order: Order) -> dict[str, Any]:
        """
        Translate internal order format to MT4-specific format.
        
        MT4 uses different field names and conventions.
        """
        # MT4 uses OP_BUY/OP_SELL for market orders
        mt4_cmd = 0 if order.direction == "long" else 1  # OP_BUY=0, OP_SELL=1
        
        mt4_order = {
            "symbol": order.symbol,
            "cmd": mt4_cmd,
            "volume": float(order.volume),
            "price": float(order.entry_price) if order.entry_price else 0,
            "slippage": 3,  # Default slippage in points
            "stoploss": float(order.stop_loss) if order.stop_loss else 0,
            "takeprofit": float(order.take_profit) if order.take_profit else 0,
            "comment": "OpenFi",
            "magic": order.magic_number or 0
        }
        
        return mt4_order
    
    def _translate_mt4_error(self, error_code: int) -> str:
        """
        Translate MT4 error codes to human-readable messages.
        
        Common MT4 error codes:
        - 1: ERR_NO_ERROR (should not happen)
        - 2: ERR_NO_RESULT
        - 4: ERR_SERVER_BUSY
        - 6: ERR_NO_CONNECTION
        - 8: ERR_TOO_FREQUENT_REQUESTS
        - 128: ERR_TRADE_TIMEOUT
        - 129: ERR_INVALID_PRICE
        - 130: ERR_INVALID_STOPS
        - 131: ERR_INVALID_TRADE_VOLUME
        - 134: ERR_NOT_ENOUGH_MONEY
        - 136: ERR_OFF_QUOTES
        - 138: ERR_REQUOTE
        - 146: ERR_TRADE_CONTEXT_BUSY
        """
        error_messages = {
            2: "No result returned from server",
            4: "Trade server is busy, please try again",
            6: "No connection to trade server",
            8: "Too frequent requests, please slow down",
            128: "Trade timeout, order not executed",
            129: "Invalid price, market may have moved",
            130: "Invalid stop loss or take profit levels",
            131: "Invalid trade volume",
            134: "Not enough money to execute trade",
            136: "Off quotes, market is closed or price unavailable",
            138: "Requote, price has changed",
            146: "Trade context is busy, try again"
        }
        
        return error_messages.get(
            error_code,
            f"MT4 error code {error_code}"
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order (placeholder)."""
        try:
            if not self.connected:
                logger.error("MT4Adapter: Not connected to broker")
                return False
            
            logger.info(f"MT4Adapter: Cancelling order {order_id}")
            await asyncio.sleep(0.05)
            logger.info(f"MT4Adapter: Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"MT4Adapter: Order cancellation failed: {e}")
            return False
    
    async def get_positions(self) -> list[Position]:
        """Get current open positions (placeholder)."""
        try:
            if not self.connected:
                logger.warning("MT4Adapter: Not connected to broker")
                return []
            
            logger.debug("MT4Adapter: Fetching open positions")
            # Placeholder: return empty list
            return []
        except Exception as e:
            logger.error(f"MT4Adapter: Failed to fetch positions: {e}")
            return []
    
    async def get_account_info(self) -> AccountInfo:
        """Get account information (placeholder)."""
        try:
            if not self.connected:
                raise Exception("Not connected to broker")
            
            logger.debug("MT4Adapter: Fetching account info")
            # Placeholder: return mock account info
            return AccountInfo(
                account_number=self.account_number or "12345678",
                balance=Decimal("10000.00"),
                equity=Decimal("10000.00"),
                margin_used=Decimal("0.00"),
                margin_free=Decimal("10000.00"),
                currency="USD"
            )
        except Exception as e:
            logger.error(f"MT4Adapter: Failed to fetch account info: {e}")
            raise

class MT5Adapter(BrokerAdapter):
    """
    MT5 broker adapter (placeholder/stub implementation).

    Full implementation will integrate with MT5 API.
    Includes connection management, error handling, and broker-specific error code translation.
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize MT5 adapter with connection configuration."""
        super().__init__(config)
        self.server = config.get("server")
        self.account_number = config.get("account_number")
        self.password = config.get("password")
        self.timeout = config.get("timeout", 30)
        self.connection_attempts = 0
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 1

    async def connect(self) -> bool:
        """Establish connection to MT5 broker with automatic reconnection."""
        try:
            logger.info(f"MT5Adapter: Connecting to broker - server={self.server}, account={self.account_number}")

            if not self.server or not self.account_number:
                logger.error("MT5Adapter: Missing required connection parameters")
                return False

            await asyncio.sleep(0.1)

            if not await self._verify_authentication():
                logger.error("MT5Adapter: Authentication failed")
                return False

            self.connected = True
            self.connection_attempts = 0
            logger.info("MT5Adapter: Connected successfully")
            return True

        except Exception as e:
            logger.error(f"MT5Adapter: Connection failed: {e}")
            self.connected = False

            if self.connection_attempts < self.max_reconnect_attempts:
                self.connection_attempts += 1
                delay = self.reconnect_delay * (2 ** (self.connection_attempts - 1))
                logger.info(f"MT5Adapter: Reconnecting in {delay}s (attempt {self.connection_attempts}/{self.max_reconnect_attempts})")
                await asyncio.sleep(delay)
                return await self.connect()

            logger.error("MT5Adapter: Max reconnection attempts reached")
            return False

    async def _verify_authentication(self) -> bool:
        """Verify authentication with broker (placeholder)."""
        await asyncio.sleep(0.05)
        return True

    async def disconnect(self) -> bool:
        """Close connection to MT5 broker."""
        try:
            logger.info("MT5Adapter: Disconnecting from broker...")
            self.connected = False
            logger.info("MT5Adapter: Disconnected successfully")
            return True
        except Exception as e:
            logger.error(f"MT5Adapter: Disconnection failed: {e}")
            return False

    async def submit_order(self, order: Order) -> OrderResult:
        """Submit order to MT5 broker with error handling."""
        try:
            if not self.connected:
                if not await self.connect():
                    return OrderResult(success=False, error_message="Not connected to broker and reconnection failed")

            logger.info(f"MT5Adapter: Submitting order - {order.symbol} {order.direction} {order.volume} @ {order.order_type}")

            validation_error = self._validate_order(order)
            if validation_error:
                return OrderResult(success=False, error_message=validation_error)

            mt5_order = self._translate_to_mt5_format(order)
            await asyncio.sleep(0.1)

            order_id = f"MT5-{uuid4().hex[:8]}"
            execution_price = order.entry_price or Decimal("1.0000")

            logger.info(f"MT5Adapter: Order submitted successfully - order_id={order_id}, execution_price={execution_price}")

            return OrderResult(success=True, order_id=order_id, execution_price=execution_price, timestamp=datetime.utcnow())

        except Exception as e:
            logger.error(f"MT5Adapter: Order submission failed: {e}")
            return OrderResult(success=False, error_message=f"Exception during order submission: {str(e)}")

    def _validate_order(self, order: Order) -> Optional[str]:
        """Validate order parameters."""
        if not order.symbol:
            return "Symbol is required"
        if order.volume <= 0:
            return "Volume must be positive"
        if order.direction not in ["long", "short"]:
            return f"Invalid direction: {order.direction}"
        if order.order_type not in ["market", "limit", "stop"]:
            return f"Invalid order type: {order.order_type}"
        return None

    def _translate_to_mt5_format(self, order: Order) -> dict[str, Any]:
        """Translate internal order format to MT5-specific format."""
        order_type_map = {
            ("long", "market"): "ORDER_TYPE_BUY",
            ("short", "market"): "ORDER_TYPE_SELL",
            ("long", "limit"): "ORDER_TYPE_BUY_LIMIT",
            ("short", "limit"): "ORDER_TYPE_SELL_LIMIT",
            ("long", "stop"): "ORDER_TYPE_BUY_STOP",
            ("short", "stop"): "ORDER_TYPE_SELL_STOP"
        }

        mt5_order_type = order_type_map.get((order.direction, order.order_type), "ORDER_TYPE_BUY")

        return {
            "action": "TRADE_ACTION_DEAL",
            "symbol": order.symbol,
            "volume": float(order.volume),
            "type": mt5_order_type,
            "price": float(order.entry_price) if order.entry_price else 0,
            "sl": float(order.stop_loss) if order.stop_loss else 0,
            "tp": float(order.take_profit) if order.take_profit else 0,
            "deviation": 10,
            "magic": order.magic_number or 0,
            "comment": "OpenFi",
            "type_time": "ORDER_TIME_GTC",
            "type_filling": "ORDER_FILLING_IOC"
        }

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order (placeholder)."""
        try:
            if not self.connected:
                logger.error("MT5Adapter: Not connected to broker")
                return False

            logger.info(f"MT5Adapter: Cancelling order {order_id}")
            await asyncio.sleep(0.05)
            logger.info(f"MT5Adapter: Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"MT5Adapter: Order cancellation failed: {e}")
            return False

    async def get_positions(self) -> list[Position]:
        """Get current open positions (placeholder)."""
        try:
            if not self.connected:
                logger.warning("MT5Adapter: Not connected to broker")
                return []

            logger.debug("MT5Adapter: Fetching open positions")
            return []
        except Exception as e:
            logger.error(f"MT5Adapter: Failed to fetch positions: {e}")
            return []

    async def get_account_info(self) -> AccountInfo:
        """Get account information (placeholder)."""
        try:
            if not self.connected:
                raise Exception("Not connected to broker")

            logger.debug("MT5Adapter: Fetching account info")
            return AccountInfo(
                account_number=self.account_number or "87654321",
                balance=Decimal("10000.00"),
                equity=Decimal("10000.00"),
                margin_used=Decimal("0.00"),
                margin_free=Decimal("10000.00"),
                currency="USD"
            )
        except Exception as e:
            logger.error(f"MT5Adapter: Failed to fetch account info: {e}")
            raise

