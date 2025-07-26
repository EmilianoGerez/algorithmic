"""
Core trading models for orders, positions, and account state.

This module defines the fundamental data structures used throughout the trading
system, including order specifications, position tracking, and account state
management.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from core.strategy.signal_models import SignalDirection

__all__ = [
    "AccountState",
    "Order",
    "OrderReceipt",
    "OrderStatus",
    "OrderType",
    "Position",
    "PositionSizing",
]


class OrderType(str, Enum):
    """Order execution types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Order execution status states."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(slots=True, frozen=True)
class PositionSizing:
    """Risk-calculated position sizing information.

    Contains all the information needed to execute a trade based on risk
    management calculations. This serves as the bridge between signal
    generation and order creation.

    Attributes:
        quantity: Number of units to trade (positive for long, negative for short)
        stop_loss: Stop loss price level
        take_profit: Take profit price level
        direction: Trade direction (LONG/SHORT)
        risk_amount: Dollar amount at risk for this trade
        entry_price: Expected entry price for the trade
        notional: Pre-computed notional value (quantity × entry_price)
    """

    quantity: Decimal
    stop_loss: float
    take_profit: float
    direction: SignalDirection
    risk_amount: float
    entry_price: float
    notional: float


@dataclass(slots=True, frozen=True)
class Order:
    """Order specification for broker execution.

    Represents a complete order ready for submission to a broker.
    Contains all necessary information for order routing and execution.

    Attributes:
        symbol: Trading symbol (e.g., "EURUSD", "BTCUSD")
        order_type: Type of order (MARKET, LIMIT, etc.)
        quantity: Quantity to trade (signed: positive=long, negative=short)
        price: Limit price (None for market orders)
        stop_loss: Stop loss price (optional)
        take_profit: Take profit price (optional)
        client_id: Client-assigned order identifier
        timestamp: Order creation timestamp
    """

    symbol: str
    order_type: OrderType
    quantity: Decimal
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    client_id: str | None = None
    timestamp: datetime | None = None


@dataclass(slots=True, frozen=True)
class OrderReceipt:
    """Broker response after order submission.

    Contains the broker's acknowledgment and tracking information
    for a submitted order.

    Attributes:
        order_id: Broker-assigned unique order identifier
        client_id: Original client order ID (if provided)
        status: Current order status
        filled_quantity: Quantity filled so far
        avg_fill_price: Average fill price for filled quantity
        timestamp: Order processing timestamp
        message: Status message or error description
    """

    order_id: str
    client_id: str | None
    status: OrderStatus
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: float | None = None
    timestamp: datetime | None = None
    message: str | None = None


@dataclass(slots=True, frozen=True)
class Position:
    """Current position in a trading symbol.

    Represents an open position with current market value and PnL tracking.
    Used for portfolio management and risk monitoring.

    Attributes:
        symbol: Trading symbol
        quantity: Current position size (signed: positive=long, negative=short)
        avg_entry_price: Average entry price for the position
        current_price: Current market price
        unrealized_pnl: Mark-to-market unrealized profit/loss
        entry_timestamp: When the position was first opened
    """

    symbol: str
    quantity: Decimal
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    entry_timestamp: datetime


@dataclass(slots=True)
class AccountState:
    """Current account state and balances.

    Tracks account equity, cash balance, and open positions for risk
    management and position sizing calculations.

    Attributes:
        cash_balance: Available cash balance
        equity: Total account equity (cash + unrealized PnL)
        positions: Currently open positions by symbol
        realized_pnl: Total realized profit/loss since account inception
        open_orders: Count of pending orders
        timestamp: Last update timestamp
    """

    cash_balance: float
    equity: float
    positions: Mapping[str, Position]
    realized_pnl: float = 0.0
    open_orders: int = 0
    timestamp: datetime | None = None

    @property
    def available_margin(self) -> float:
        """Calculate available margin for new positions.

        For simplicity, this returns the current cash balance.
        In a real implementation, this would account for margin requirements
        and position-specific margin calculations.

        Returns:
            Available margin amount for new positions.
        """
        return self.cash_balance

    @property
    def total_unrealized_pnl(self) -> float:
        """Calculate total unrealized PnL across all positions.

        Returns:
            Sum of unrealized PnL for all open positions.
        """
        return sum(pos.unrealized_pnl for pos in self.positions.values())
