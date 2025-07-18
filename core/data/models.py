"""
Core Data Models

Universal data structures for the trading system.
These models are platform-agnostic and represent the core business entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class TimeFrame(Enum):
    """Supported timeframes"""

    TICK = "tick"
    SECOND_15 = "15s"
    SECOND_30 = "30s"
    MINUTE_1 = "1min"
    MINUTE_5 = "5min"
    MINUTE_15 = "15min"
    MINUTE_30 = "30min"
    HOUR_1 = "1H"
    HOUR_4 = "4H"
    DAY_1 = "1D"
    WEEK_1 = "1W"
    MONTH_1 = "1M"


class SignalDirection(Enum):
    """Signal direction"""

    LONG = "long"
    SHORT = "short"


class SignalType(Enum):
    """Signal types"""

    ENTRY = "entry"
    EXIT = "exit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    """Order status"""

    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Candle:
    """Single candlestick data"""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    symbol: str
    timeframe: TimeFrame

    def __post_init__(self):
        """Validate candle data"""
        if self.high < max(self.open, self.close):
            raise ValueError("High must be >= max(open, close)")
        if self.low > min(self.open, self.close):
            raise ValueError("Low must be <= min(open, close)")
        if self.volume < 0:
            raise ValueError("Volume must be non-negative")


@dataclass
class MarketData:
    """Collection of market data"""

    symbol: str
    timeframe: TimeFrame
    candles: List[Candle] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_candle(self, candle: Candle) -> None:
        """Add a new candle to the data"""
        if candle.symbol != self.symbol:
            raise ValueError(
                f"Candle symbol {candle.symbol} doesn't match {self.symbol}"
            )
        if candle.timeframe != self.timeframe:
            raise ValueError(
                f"Candle timeframe {candle.timeframe} doesn't match {self.timeframe}"
            )

        self.candles.append(candle)
        # Keep candles sorted by timestamp
        self.candles.sort(key=lambda c: c.timestamp)

    def get_latest_candle(self) -> Optional[Candle]:
        """Get the most recent candle"""
        return self.candles[-1] if self.candles else None

    def get_candles_range(self, start: datetime, end: datetime) -> List[Candle]:
        """Get candles within a time range"""
        return [candle for candle in self.candles if start <= candle.timestamp <= end]


@dataclass
class Signal:
    """Standardized trading signal"""

    timestamp: datetime
    symbol: str
    direction: SignalDirection
    signal_type: SignalType
    entry_price: Decimal
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    confidence: float = 0.0  # 0.0 to 1.0
    strength: float = 0.0  # 0.0 to 1.0
    strategy_name: str = ""
    timeframe: TimeFrame = TimeFrame.MINUTE_15
    risk_reward_ratio: float = 2.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate signal data"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("Strength must be between 0.0 and 1.0")
        if self.entry_price <= 0:
            raise ValueError("Entry price must be positive")
        if self.stop_loss and self.stop_loss <= 0:
            raise ValueError("Stop loss must be positive")
        if self.take_profit and self.take_profit <= 0:
            raise ValueError("Take profit must be positive")

    def calculate_risk_amount(self) -> Optional[Decimal]:
        """Calculate risk amount per unit"""
        if self.stop_loss is None:
            return None
        return abs(self.entry_price - self.stop_loss)

    def calculate_reward_amount(self) -> Optional[Decimal]:
        """Calculate reward amount per unit"""
        if self.take_profit is None:
            return None
        return abs(self.take_profit - self.entry_price)

    def get_actual_risk_reward_ratio(self) -> Optional[float]:
        """Get actual risk/reward ratio"""
        risk = self.calculate_risk_amount()
        reward = self.calculate_reward_amount()
        if risk is None or reward is None or risk == 0:
            return None
        return float(reward / risk)


@dataclass
class Position:
    """Trading position"""

    symbol: str
    direction: SignalDirection
    entry_price: Decimal
    quantity: Decimal
    entry_time: datetime
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    status: str = "open"
    strategy_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_current_price(self, price: Decimal) -> None:
        """Update current price and unrealized PnL"""
        self.current_price = price
        if self.direction == SignalDirection.LONG:
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.quantity

    def close_position(self, exit_price: Decimal, exit_time: datetime) -> None:
        """Close the position"""
        self.realized_pnl = self.unrealized_pnl
        self.status = "closed"
        self.metadata.update({"exit_price": exit_price, "exit_time": exit_time})


@dataclass
class Order:
    """Trading order"""

    order_id: str
    symbol: str
    direction: SignalDirection
    quantity: Decimal
    price: Optional[Decimal] = None  # None for market orders
    order_type: str = "market"  # market, limit, stop, stop_limit
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    filled_price: Optional[Decimal] = None
    filled_quantity: Decimal = Decimal("0")
    strategy_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FVGZone:
    """Fair Value Gap zone"""

    timestamp: datetime
    symbol: str
    timeframe: TimeFrame
    direction: SignalDirection
    zone_high: Decimal
    zone_low: Decimal
    strength: float
    confidence: float
    status: str = "active"  # active, touched, invalidated
    touch_count: int = 0
    created_candle_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate FVG zone data"""
        if self.zone_high <= self.zone_low:
            raise ValueError("Zone high must be greater than zone low")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("Strength must be between 0.0 and 1.0")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

    def is_price_in_zone(self, price: Decimal) -> bool:
        """Check if price is within the FVG zone"""
        return self.zone_low <= price <= self.zone_high

    def get_zone_size(self) -> Decimal:
        """Get the size of the FVG zone"""
        return self.zone_high - self.zone_low

    def get_zone_midpoint(self) -> Decimal:
        """Get the midpoint of the FVG zone"""
        return (self.zone_high + self.zone_low) / 2


@dataclass
class StrategyConfig:
    """Base strategy configuration"""

    name: str
    symbol: str
    timeframes: List[TimeFrame]
    risk_per_trade: float = 0.02  # 2% risk per trade
    risk_reward_ratio: float = 2.0
    max_positions: int = 1
    confidence_threshold: float = 0.85
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration"""
        if not 0.0 < self.risk_per_trade <= 1.0:
            raise ValueError("Risk per trade must be between 0.0 and 1.0")
        if self.risk_reward_ratio <= 0:
            raise ValueError("Risk reward ratio must be positive")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")


@dataclass
class BacktestResult:
    """Backtesting result"""

    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    final_capital: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    signals: List[Signal] = field(default_factory=list)
    trades: List[Position] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_return_percentage(self) -> float:
        """Calculate total return percentage"""
        if self.initial_capital == 0:
            return 0.0
        return float(
            (self.final_capital - self.initial_capital) / self.initial_capital * 100
        )

    def calculate_win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
