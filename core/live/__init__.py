"""
Live Trading Engine

Real-time trading execution system that integrates with brokers and exchanges.
Provides order management, position tracking, and risk monitoring for live trading.
."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Optional

from ..data.models import (
    Order,
    OrderStatus,
    Position,
    Signal,
    SignalDirection,
    SignalType,
)
from ..risk import RiskManager


class ExecutionMode(Enum):
    """Live trading execution modes."""

    PAPER = "paper"  # Paper trading (simulation)
    LIVE = "live"  # Live trading with real money
    SANDBOX = "sandbox"  # Broker sandbox environment


@dataclass
class LiveTradingConfig:
    """Configuration for live trading."""

    mode: ExecutionMode = ExecutionMode.PAPER
    max_orders_per_minute: int = 10
    max_daily_trades: int = 50
    heartbeat_interval: float = 30.0  # seconds
    order_timeout: float = 60.0  # seconds
    risk_check_interval: float = 5.0  # seconds
    enable_auto_trading: bool = True
    enable_position_management: bool = True
    emergency_stop_loss: float = 0.05  # 5% portfolio loss triggers emergency stop

    def __post_init__(self):
        if self.max_orders_per_minute <= 0:
            raise ValueError("Max orders per minute must be positive")
        if self.max_daily_trades <= 0:
            raise ValueError("Max daily trades must be positive")


@dataclass
class TradingState:
    """Current state of the live trading system."""

    is_running: bool = False
    is_emergency_stopped: bool = False
    last_heartbeat: Optional[datetime] = None
    orders_sent_today: int = 0
    orders_sent_this_minute: int = 0
    last_minute_reset: datetime = field(default_factory=datetime.now)
    active_orders: list[Order] = field(default_factory=list)
    filled_orders: list[Order] = field(default_factory=list)
    error_count: int = 0
    last_error: Optional[str] = None

    def reset_daily_counters(self):
        """Reset daily counters at start of new trading day."""
        self.orders_sent_today = 0
        self.error_count = 0
        self.last_error = None

    def increment_order_count(self):
        """Increment order counters with rate limiting."""
        now = datetime.now()

        # Reset minute counter if needed
        if (now - self.last_minute_reset).total_seconds() >= 60:
            self.orders_sent_this_minute = 0
            self.last_minute_reset = now

        self.orders_sent_this_minute += 1
        self.orders_sent_today += 1


class BrokerAdapter(ABC):
    """Abstract base class for broker integrations."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to broker API."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker API."""

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to broker."""

    @abstractmethod
    async def place_order(self, order: Order) -> str:
        """Place an order and return order ID."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get order status."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get current positions."""

    @abstractmethod
    async def get_account_balance(self) -> Decimal:
        """Get account balance."""

    @abstractmethod
    async def get_buying_power(self) -> Decimal:
        """Get available buying power."""


class PaperBrokerAdapter(BrokerAdapter):
    """Paper trading broker adapter for simulation."""

    def __init__(self, initial_balance: Decimal = Decimal("100000")):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        self.is_connected_flag = False
        self.current_prices: Dict[str, Decimal] = {}

    async def connect(self) -> bool:
        """Connect to paper trading system."""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.is_connected_flag = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from paper trading system."""
        await asyncio.sleep(0.1)
        self.is_connected_flag = False

    async def is_connected(self) -> bool:
        """Check connection status."""
        return self.is_connected_flag

    async def place_order(self, order: Order) -> str:
        """Place a paper order."""
        if not self.is_connected_flag:
            raise RuntimeError("Not connected to broker")

        # Generate order ID
        self.order_counter += 1
        order_id = f"PAPER_{self.order_counter:06d}"

        # Create order copy with ID
        order_copy = Order(
            order_id=order_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            price=order.price,
            order_type=order.order_type,
            status=OrderStatus.PENDING,
            strategy_name=order.strategy_name,
            metadata=order.metadata.copy(),
        )

        self.orders[order_id] = order_copy

        # Simulate immediate fill for market orders
        if order.order_type == "market":
            await self._simulate_fill(order_id)

        return order_id

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a paper order."""
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                return True
        return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get paper order status."""
        if order_id in self.orders:
            return self.orders[order_id].status
        return OrderStatus.REJECTED

    async def get_positions(self) -> list[Position]:
        """Get paper trading positions."""
        return list(self.positions.values())

    async def get_account_balance(self) -> Decimal:
        """Get paper trading balance."""
        return self.balance

    async def get_buying_power(self) -> Decimal:
        """Get paper trading buying power."""
        return self.balance  # Simplified: assume no margin

    async def _simulate_fill(self, order_id: str) -> None:
        """Simulate order fill."""
        await asyncio.sleep(0.05)  # Simulate execution delay

        order = self.orders[order_id]

        # Use current market price or order price
        fill_price = self.current_prices.get(
            order.symbol, order.price or Decimal("100")
        )

        # Apply simple slippage
        slippage = Decimal("0.001")  # 0.1% slippage
        if order.direction == SignalDirection.LONG:
            fill_price += fill_price * slippage
        else:
            fill_price -= fill_price * slippage

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now()
        order.filled_price = fill_price
        order.filled_quantity = order.quantity

        # Update position
        position_key = order.symbol
        if position_key in self.positions:
            # Update existing position
            position = self.positions[position_key]
            if position.direction == order.direction:
                # Add to position
                total_quantity = position.quantity + order.quantity
                weighted_price = (
                    (position.entry_price * position.quantity)
                    + (fill_price * order.quantity)
                ) / total_quantity
                position.quantity = total_quantity
                position.entry_price = weighted_price
            else:
                # Reduce or reverse position
                if order.quantity >= position.quantity:
                    # Close or reverse position
                    remaining_quantity = order.quantity - position.quantity
                    if remaining_quantity > 0:
                        # Reverse position
                        position.direction = order.direction
                        position.quantity = remaining_quantity
                        position.entry_price = fill_price
                        position.entry_time = datetime.now()
                    else:
                        # Close position
                        del self.positions[position_key]
                else:
                    # Reduce position
                    position.quantity -= order.quantity
        else:
            # Create new position
            self.positions[position_key] = Position(
                symbol=order.symbol,
                direction=order.direction,
                entry_price=fill_price,
                quantity=order.quantity,
                entry_time=datetime.now(),
                strategy_name=order.strategy_name,
            )

        # Update balance
        trade_value = fill_price * order.quantity
        if order.direction == SignalDirection.LONG:
            self.balance -= trade_value
        else:
            self.balance += trade_value

    def update_market_price(self, symbol: str, price: Decimal) -> None:
        """Update market price for simulation."""
        self.current_prices[symbol] = price

        # Update position P&L
        if symbol in self.positions:
            position = self.positions[symbol]
            position.update_current_price(price)


class LiveTradingEngine:
    """Main live trading engine."""

    def __init__(
        self,
        broker_adapter: BrokerAdapter,
        risk_manager: RiskManager,
        config: LiveTradingConfig,
    ):
        self.broker = broker_adapter
        self.risk_manager = risk_manager
        self.config = config
        self.state = TradingState()

        # Event handlers
        self.signal_handlers: list[Callable[[Signal], None]] = []
        self.order_handlers: list[Callable[[Order], None]] = []
        self.position_handlers: list[Callable[[Position], None]] = []
        self.error_handlers: list[Callable[[str], None]] = []

        # Background tasks
        self._background_tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

        # Order management
        self.pending_orders: Dict[str, Order] = {}
        self.order_timeouts: Dict[str, datetime] = {}

        # Performance tracking
        self.daily_pnl = Decimal("0")
        self.start_balance = Decimal("0")

    async def start(self) -> bool:
        """Start the live trading engine."""
        try:
            # Connect to broker
            if not await self.broker.connect():
                self.state.last_error = "Failed to connect to broker"
                return False

            # Initialize state
            self.state.is_running = True
            self.state.is_emergency_stopped = False
            self.state.last_heartbeat = datetime.now()
            self.start_balance = await self.broker.get_account_balance()

            # Start background tasks
            self._start_background_tasks()

            print(f"✅ Live Trading Engine started in {self.config.mode.value} mode")
            return True

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.state.last_error = str(exc)
            self.state.error_count += 1
            self._notify_error(f"Failed to start trading engine: {exc}")
            return False

    async def stop(self) -> None:
        """Stop the live trading engine."""
        print("🛑 Stopping Live Trading Engine...")

        self.state.is_running = False
        self._shutdown_event.set()

        # Cancel all pending orders
        await self._cancel_all_orders()

        # Wait for background tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        # Disconnect from broker
        await self.broker.disconnect()

        print("✅ Live Trading Engine stopped")

    async def process_signal(self, signal: Signal) -> Optional[Order]:
        """Process a trading signal."""
        if not self.state.is_running or self.state.is_emergency_stopped:
            return None

        try:
            # Check rate limits
            if not self._check_rate_limits():
                return None

            # Evaluate signal with risk management
            assessment = self.risk_manager.evaluate_signal(signal)

            if not assessment["approved"]:
                print(f"❌ Signal rejected: {', '.join(assessment['reasons'])}")
                return None

            # Create order
            order = self._create_order_from_signal(signal, assessment["position_size"])

            # Place order
            order_id = await self.broker.place_order(order)
            order.order_id = order_id

            # Track order
            self.pending_orders[order_id] = order
            self.order_timeouts[order_id] = datetime.now() + timedelta(
                seconds=self.config.order_timeout
            )

            # Update counters
            self.state.increment_order_count()

            # Notify handlers
            self._notify_order_placed(order)

            print(
                f"📋 Order placed: {order.symbol} {order.direction.value} "
                f"{order.quantity} @ {order.price}"
            )
            return order

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.state.error_count += 1
            self.state.last_error = str(exc)
            self._notify_error(f"Error processing signal: {exc}")
            return None

    async def emergency_stop(self, reason: str) -> None:
        """Emergency stop all trading."""
        print(f"🚨 EMERGENCY STOP: {reason}")

        self.state.is_emergency_stopped = True

        # Cancel all orders
        await self._cancel_all_orders()

        # Close all positions (if configured)
        if self.config.enable_position_management:
            await self._close_all_positions()

        # Notify handlers
        self._notify_error(f"Emergency stop triggered: {reason}")

    def add_signal_handler(self, handler: Callable[[Signal], None]) -> None:
        """Add signal event handler."""
        self.signal_handlers.append(handler)

    def add_order_handler(self, handler: Callable[[Order], None]) -> None:
        """Add order event handler."""
        self.order_handlers.append(handler)

    def add_position_handler(self, handler: Callable[[Position], None]) -> None:
        """Add position event handler."""
        self.position_handlers.append(handler)

    def add_error_handler(self, handler: Callable[[str], None]) -> None:
        """Add error event handler."""
        self.error_handlers.append(handler)

    def _start_background_tasks(self) -> None:
        """Start background monitoring tasks."""
        self._background_tasks = [
            asyncio.create_task(self._heartbeat_task()),
            asyncio.create_task(self._order_monitoring_task()),
            asyncio.create_task(self._risk_monitoring_task()),
            asyncio.create_task(self._position_monitoring_task()),
        ]

    async def _heartbeat_task(self) -> None:
        """Heartbeat task to monitor system health."""
        while self.state.is_running and not self._shutdown_event.is_set():
            try:
                # Update heartbeat
                self.state.last_heartbeat = datetime.now()

                # Check broker connection
                if not await self.broker.is_connected():
                    await self.emergency_stop("Lost broker connection")
                    break

                await asyncio.sleep(self.config.heartbeat_interval)

            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._notify_error(f"Heartbeat error: {exc}")
                await asyncio.sleep(5)

    async def _order_monitoring_task(self) -> None:
        """Monitor pending orders."""
        while self.state.is_running and not self._shutdown_event.is_set():
            try:
                current_time = datetime.now()
                expired_orders = []

                for order_id, order in self.pending_orders.items():
                    # Check order status
                    status = await self.broker.get_order_status(order_id)

                    if status == OrderStatus.FILLED:
                        # Order filled
                        order.status = status
                        order.filled_at = current_time
                        self.state.filled_orders.append(order)
                        expired_orders.append(order_id)
                        self._notify_order_filled(order)

                    elif (
                        status == OrderStatus.CANCELLED
                        or status == OrderStatus.REJECTED
                    ):
                        # Order cancelled or rejected
                        order.status = status
                        expired_orders.append(order_id)
                        self._notify_order_cancelled(order)

                    elif current_time > self.order_timeouts.get(order_id, current_time):
                        # Order timeout
                        await self.broker.cancel_order(order_id)
                        expired_orders.append(order_id)
                        self._notify_error(f"Order timeout: {order_id}")

                # Remove expired orders
                for order_id in expired_orders:
                    self.pending_orders.pop(order_id, None)
                    self.order_timeouts.pop(order_id, None)

                await asyncio.sleep(1)  # Check every second

            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._notify_error(f"Order monitoring error: {exc}")
                await asyncio.sleep(5)

    async def _risk_monitoring_task(self) -> None:
        """Monitor risk metrics."""
        while self.state.is_running and not self._shutdown_event.is_set():
            try:
                # Update account balance
                current_balance = await self.broker.get_account_balance()

                # Calculate daily P&L
                self.daily_pnl = current_balance - self.start_balance
                daily_loss_pct = float(self.daily_pnl / self.start_balance)

                # Check emergency stop conditions
                if daily_loss_pct <= -self.config.emergency_stop_loss:
                    await self.emergency_stop(
                        f"Daily loss limit exceeded: {daily_loss_pct:.2%}"
                    )
                    break

                # Update risk manager
                positions = await self.broker.get_positions()
                current_prices = {
                    pos.symbol: pos.current_price
                    for pos in positions
                    if pos.current_price
                }
                self.risk_manager.update_positions(current_prices)

                # Check if trading should be stopped
                if self.risk_manager.should_stop_trading():
                    await self.emergency_stop("Risk limits exceeded")
                    break

                await asyncio.sleep(self.config.risk_check_interval)

            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._notify_error(f"Risk monitoring error: {exc}")
                await asyncio.sleep(5)

    async def _position_monitoring_task(self) -> None:
        """Monitor positions."""
        while self.state.is_running and not self._shutdown_event.is_set():
            try:
                positions = await self.broker.get_positions()

                for position in positions:
                    self._notify_position_update(position)

                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._notify_error(f"Position monitoring error: {exc}")
                await asyncio.sleep(5)

    def _check_rate_limits(self) -> bool:
        """Check if we can place more orders."""
        if self.state.orders_sent_this_minute >= self.config.max_orders_per_minute:
            return False
        if self.state.orders_sent_today >= self.config.max_daily_trades:
            return False
        return True

    def _create_order_from_signal(
        self, signal: Signal, position_size: Decimal
    ) -> Order:
        """Create order from signal."""
        return Order(
            order_id="",  # Will be set when placed
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=position_size,
            price=(
                signal.entry_price if signal.signal_type == SignalType.ENTRY else None
            ),
            order_type=(
                "market" if signal.signal_type == SignalType.ENTRY else "limit"
            ),
            strategy_name=signal.strategy_name,
            metadata={
                "signal_confidence": signal.confidence,
                "signal_strength": signal.strength,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
            },
        )

    async def _cancel_all_orders(self) -> None:
        """Cancel all pending orders."""
        for order_id in list(self.pending_orders.keys()):
            try:
                await self.broker.cancel_order(order_id)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._notify_error(f"Error cancelling order {order_id}: {exc}")

    async def _close_all_positions(self) -> None:
        """Close all positions."""
        try:
            positions = await self.broker.get_positions()
            for position in positions:
                # Create closing order
                closing_order = Order(
                    order_id="",
                    symbol=position.symbol,
                    direction=(
                        SignalDirection.SHORT
                        if position.direction == SignalDirection.LONG
                        else SignalDirection.LONG
                    ),
                    quantity=position.quantity,
                    order_type="market",
                    strategy_name="emergency_close",
                )

                await self.broker.place_order(closing_order)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._notify_error(f"Error closing positions: {exc}")

    def _notify_order_placed(self, order: Order) -> None:
        """Notify order placed."""
        for handler in self.order_handlers:
            try:
                handler(order)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in order handler: {exc}")

    def _notify_order_filled(self, order: Order) -> None:
        """Notify order filled."""
        print(
            f"✅ Order filled: {order.symbol} {order.direction.value} "
            f"{order.quantity} @ {order.filled_price}"
        )
        for handler in self.order_handlers:
            try:
                handler(order)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in order handler: {exc}")

    def _notify_order_cancelled(self, order: Order) -> None:
        """Notify order cancelled."""
        print(
            f"❌ Order cancelled: {order.symbol} {order.direction.value} "
            f"{order.quantity}"
        )
        for handler in self.order_handlers:
            try:
                handler(order)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in order handler: {exc}")

    def _notify_position_update(self, position: Position) -> None:
        """Notify position update."""
        for handler in self.position_handlers:
            try:
                handler(position)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in position handler: {exc}")

    def _notify_error(self, error: str) -> None:
        """Notify error."""
        print(f"❌ Error: {error}")
        for handler in self.error_handlers:
            try:
                handler(error)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in error handler: {exc}")

    def get_status(self) -> Dict[str, Any]:
        """Get current trading status."""
        return {
            "is_running": self.state.is_running,
            "is_emergency_stopped": self.state.is_emergency_stopped,
            "mode": self.config.mode.value,
            "last_heartbeat": self.state.last_heartbeat,
            "orders_sent_today": self.state.orders_sent_today,
            "orders_sent_this_minute": self.state.orders_sent_this_minute,
            "pending_orders": len(self.pending_orders),
            "filled_orders": len(self.state.filled_orders),
            "error_count": self.state.error_count,
            "last_error": self.state.last_error,
            "daily_pnl": self.daily_pnl,
            "auto_trading_enabled": self.config.enable_auto_trading,
        }
