"""
Risk Management System

Comprehensive risk management including position sizing, portfolio management,
and risk controls for the trading system.
."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from ..data.models import Position, Signal, SignalDirection


@dataclass
class RiskLimits:
    """Risk limits configuration."""

    max_position_size: Decimal = Decimal("0.1")  # 10% of portfolio
    max_daily_loss: Decimal = Decimal("0.05")  # 5% daily loss limit
    max_drawdown: Decimal = Decimal("0.2")  # 20% max drawdown
    max_positions: int = 10
    max_correlation: float = 0.7  # Maximum correlation between positions
    leverage_limit: Decimal = Decimal("1.0")  # No leverage by default

    def __post_init__(self):
        """Validate risk limits."""
        if self.max_position_size <= 0 or self.max_position_size > 1:
            raise ValueError("Max position size must be between 0 and 1")
        if self.max_daily_loss <= 0 or self.max_daily_loss > 1:
            raise ValueError("Max daily loss must be between 0 and 1")
        if self.max_drawdown <= 0 or self.max_drawdown > 1:
            raise ValueError("Max drawdown must be between 0 and 1")


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics."""

    total_value: Decimal = Decimal("0")
    available_cash: Decimal = Decimal("0")
    invested_capital: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    daily_pnl: Decimal = Decimal("0")
    drawdown: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    portfolio_beta: float = 1.0
    sharpe_ratio: Optional[float] = None
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0

    def update_win_rate(self):
        """Update win rate calculation."""
        if self.total_trades > 0:
            self.win_rate = self.winning_trades / self.total_trades
        else:
            self.win_rate = 0.0


class PositionSizer(ABC):
    """Abstract base class for position sizing algorithms."""

    @abstractmethod
    def calculate_position_size(
        self,
        signal: Signal,
        account_balance: Decimal,
        risk_limits: RiskLimits,
        current_positions: list[Position],
    ) -> Decimal:
        """Calculate position size for a signal."""


class FixedRiskPositionSizer(PositionSizer):
    """Fixed risk position sizing - risk a fixed percentage per trade."""

    def __init__(self, risk_per_trade: float = 0.02):
        self.risk_per_trade = risk_per_trade

    def calculate_position_size(
        self,
        signal: Signal,
        account_balance: Decimal,
        risk_limits: RiskLimits,
        current_positions: list[Position],
    ) -> Decimal:
        """Calculate position size based on fixed risk percentage."""
        if signal.stop_loss is None:
            # No stop loss = no position
            return Decimal("0")

        # Calculate risk per unit
        risk_per_unit = abs(signal.entry_price - signal.stop_loss)
        if risk_per_unit == 0:
            return Decimal("0")

        # Calculate position size based on risk
        risk_amount = account_balance * Decimal(str(self.risk_per_trade))
        position_size = risk_amount / risk_per_unit

        # Apply position size limits
        max_position_value = account_balance * risk_limits.max_position_size
        max_position_size = max_position_value / signal.entry_price

        # Return the smaller of the two
        return min(position_size, max_position_size)


class VolatilityPositionSizer(PositionSizer):
    """Volatility-based position sizing using ATR."""

    def __init__(self, base_risk: float = 0.02, volatility_multiplier: float = 2.0):
        self.base_risk = base_risk
        self.volatility_multiplier = volatility_multiplier

    def calculate_position_size(
        self,
        signal: Signal,
        account_balance: Decimal,
        risk_limits: RiskLimits,
        current_positions: list[Position],
    ) -> Decimal:
        """Calculate position size based on volatility."""
        # Get ATR from signal metadata if available
        atr = signal.metadata.get("atr", None)
        if atr is None:
            # Fall back to fixed risk sizing
            return FixedRiskPositionSizer(self.base_risk).calculate_position_size(
                signal, account_balance, risk_limits, current_positions
            )

        # Calculate stop loss based on ATR if not provided
        stop_loss = signal.stop_loss
        if stop_loss is None:
            atr_decimal = Decimal(str(atr))
            if signal.direction == SignalDirection.LONG:
                stop_loss = signal.entry_price - (
                    atr_decimal * Decimal(str(self.volatility_multiplier))
                )
            else:
                stop_loss = signal.entry_price + (
                    atr_decimal * Decimal(str(self.volatility_multiplier))
                )

        # Calculate position size
        risk_per_unit = abs(signal.entry_price - stop_loss)
        if risk_per_unit == 0:
            return Decimal("0")

        risk_amount = account_balance * Decimal(str(self.base_risk))
        position_size = risk_amount / risk_per_unit

        # Apply limits
        max_position_value = account_balance * risk_limits.max_position_size
        max_position_size = max_position_value / signal.entry_price

        return min(position_size, max_position_size)


class KellyPositionSizer(PositionSizer):
    """Kelly Criterion position sizing."""

    def __init__(self, lookback_trades: int = 50, max_kelly: float = 0.25):
        self.lookback_trades = lookback_trades
        self.max_kelly = max_kelly

    def calculate_position_size(
        self,
        signal: Signal,
        account_balance: Decimal,
        risk_limits: RiskLimits,
        current_positions: list[Position],
    ) -> Decimal:
        """Calculate position size using Kelly Criterion."""
        # Get historical performance from signal metadata
        win_rate = signal.metadata.get("win_rate", 0.5)
        avg_win = signal.metadata.get("avg_win", 1.0)
        avg_loss = signal.metadata.get("avg_loss", 1.0)

        if avg_loss == 0:
            return Decimal("0")

        # Calculate Kelly percentage
        # Kelly = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_rate, q = 1 - win_rate
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - win_rate

        kelly_pct = (b * p - q) / b

        # Apply maximum Kelly limit
        kelly_pct = min(kelly_pct, self.max_kelly)
        kelly_pct = max(kelly_pct, 0.01)  # Minimum 1%

        # Calculate position size
        position_value = account_balance * Decimal(str(kelly_pct))
        position_size = position_value / signal.entry_price

        # Apply limits
        max_position_value = account_balance * risk_limits.max_position_size
        max_position_size = max_position_value / signal.entry_price

        return min(position_size, max_position_size)


class RiskManager:
    """Main risk management system."""

    def __init__(
        self,
        risk_limits: RiskLimits,
        position_sizer: PositionSizer,
        initial_capital: Decimal,
    ):
        self.risk_limits = risk_limits
        self.position_sizer = position_sizer
        self.initial_capital = initial_capital

        # Portfolio state
        self.positions: list[Position] = []
        self.metrics = PortfolioMetrics()
        self.metrics.total_value = initial_capital
        self.metrics.available_cash = initial_capital

        # Risk tracking
        self.daily_start_balance = initial_capital
        self.peak_balance = initial_capital
        self.trade_history: list[Dict] = []

    def evaluate_signal(self, signal: Signal) -> Dict[str, any]:
        """Evaluate a signal and return risk assessment."""
        assessment = {
            "signal": signal,
            "approved": False,
            "position_size": Decimal("0"),
            "risk_amount": Decimal("0"),
            "reasons": [],
        }

        # Check if we can take new positions
        if len(self.positions) >= self.risk_limits.max_positions:
            assessment["reasons"].append("Maximum positions reached")
            return assessment

        # Check daily loss limit
        if (
            self.metrics.daily_pnl
            <= -self.risk_limits.max_daily_loss * self.daily_start_balance
        ):
            assessment["reasons"].append("Daily loss limit exceeded")
            return assessment

        # Check drawdown limit
        if self.metrics.drawdown >= self.risk_limits.max_drawdown:
            assessment["reasons"].append("Maximum drawdown exceeded")
            return assessment

        # Check if we already have a position in this symbol
        existing_position = self.get_position_by_symbol(signal.symbol)
        if existing_position:
            assessment["reasons"].append("Position already exists for this symbol")
            return assessment

        # Calculate position size
        position_size = self.position_sizer.calculate_position_size(
            signal,
            self.metrics.available_cash,
            self.risk_limits,
            self.positions,
        )

        if position_size <= 0:
            assessment["reasons"].append("Position size is zero or negative")
            return assessment

        # Calculate required capital
        required_capital = position_size * signal.entry_price

        # Check if we have enough capital
        if required_capital > self.metrics.available_cash:
            assessment["reasons"].append("Insufficient capital")
            return assessment

        # Calculate risk amount
        if signal.stop_loss:
            risk_amount = position_size * abs(signal.entry_price - signal.stop_loss)
        else:
            risk_amount = required_capital * Decimal("0.02")  # Default 2% risk

        # Signal approved
        assessment["approved"] = True
        assessment["position_size"] = position_size
        assessment["risk_amount"] = risk_amount
        assessment["required_capital"] = required_capital

        return assessment

    def add_position(self, signal: Signal, position_size: Decimal) -> Position:
        """Add a new position to the portfolio."""
        position = Position(
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=signal.entry_price,
            quantity=position_size,
            entry_time=signal.timestamp,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy_name=signal.strategy_name,
        )

        self.positions.append(position)

        # Update cash
        required_capital = position_size * signal.entry_price
        self.metrics.available_cash -= required_capital
        self.metrics.invested_capital += required_capital

        return position

    def close_position(
        self, position: Position, exit_price: Decimal, exit_time: datetime
    ) -> None:
        """Close a position and update metrics."""
        position.close_position(exit_price, exit_time)

        # Update portfolio metrics
        self.metrics.realized_pnl += position.realized_pnl
        self.metrics.invested_capital -= position.quantity * position.entry_price
        self.metrics.available_cash += position.quantity * exit_price

        # Update trade statistics
        self.metrics.total_trades += 1
        if position.realized_pnl > 0:
            self.metrics.winning_trades += 1

        self.metrics.update_win_rate()

        # Record trade
        self.trade_history.append(
            {
                "symbol": position.symbol,
                "direction": position.direction,
                "entry_price": position.entry_price,
                "exit_price": exit_price,
                "quantity": position.quantity,
                "pnl": position.realized_pnl,
                "entry_time": position.entry_time,
                "exit_time": exit_time,
                "strategy": position.strategy_name,
            }
        )

        # Remove from active positions
        self.positions.remove(position)

    def update_positions(self, current_prices: Dict[str, Decimal]) -> None:
        """Update all positions with current prices."""
        total_unrealized_pnl = Decimal("0")

        for position in self.positions:
            if position.symbol in current_prices:
                position.update_current_price(current_prices[position.symbol])
                total_unrealized_pnl += position.unrealized_pnl

        self.metrics.unrealized_pnl = total_unrealized_pnl
        self.metrics.total_value = (
            self.metrics.available_cash
            + self.metrics.invested_capital
            + self.metrics.unrealized_pnl
        )

        # Update drawdown
        if self.metrics.total_value > self.peak_balance:
            self.peak_balance = self.metrics.total_value

        self.metrics.drawdown = (
            self.peak_balance - self.metrics.total_value
        ) / self.peak_balance
        if self.metrics.drawdown > self.metrics.max_drawdown:
            self.metrics.max_drawdown = self.metrics.drawdown

    def get_position_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        for position in self.positions:
            if position.symbol == symbol:
                return position
        return None

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary."""
        return {
            "total_value": self.metrics.total_value,
            "available_cash": self.metrics.available_cash,
            "invested_capital": self.metrics.invested_capital,
            "unrealized_pnl": self.metrics.unrealized_pnl,
            "realized_pnl": self.metrics.realized_pnl,
            "daily_pnl": self.metrics.daily_pnl,
            "drawdown": self.metrics.drawdown,
            "max_drawdown": self.metrics.max_drawdown,
            "total_trades": self.metrics.total_trades,
            "winning_trades": self.metrics.winning_trades,
            "win_rate": self.metrics.win_rate,
            "active_positions": len(self.positions),
            "return_pct": float(
                (self.metrics.total_value - self.initial_capital)
                / self.initial_capital
                * 100
            ),
        }

    def reset_daily_metrics(self) -> None:
        """Reset daily metrics (call at start of each trading day)."""
        self.daily_start_balance = self.metrics.total_value
        self.metrics.daily_pnl = Decimal("0")

    def should_stop_trading(self) -> bool:
        """Check if trading should be stopped due to risk limits."""
        return (
            self.metrics.daily_pnl
            <= -self.risk_limits.max_daily_loss * self.daily_start_balance
            or self.metrics.drawdown >= self.risk_limits.max_drawdown
        )
