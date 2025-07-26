"""
Risk manager implementation for position sizing and trade risk calculation.

This module provides the main RiskManager class that calculates position sizes
based on account state, risk parameters, and current market conditions.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from core.strategy.signal_models import SignalDirection, TradingSignal
from core.trading.models import AccountState, PositionSizing

from .config import RiskConfig, RiskModel

if TYPE_CHECKING:
    from core.indicators.snapshot import IndicatorSnapshot

__all__ = ["RiskManager"]

logger = logging.getLogger(__name__)


class RiskManager:
    """Risk manager for position sizing and trade validation.

    The RiskManager calculates appropriate position sizes based on account
    state, risk configuration, and current market conditions. It supports
    both ATR-based and percentage-based risk models.

    The manager ensures trades stay within risk limits and calculates
    stop loss and take profit levels based on the configured risk model.
    """

    def __init__(self, config: RiskConfig) -> None:
        """Initialize risk manager with configuration.

        Args:
            config: Risk management configuration parameters.
        """
        self.config = config
        self._logger = logger.getChild(self.__class__.__name__)

    def size(
        self,
        signal: TradingSignal,
        account: AccountState,
        snapshot: IndicatorSnapshot,
    ) -> PositionSizing | None:
        """Calculate position sizing for a trading signal.

        Determines the appropriate position size based on the configured
        risk model, account state, and current market conditions.

        Args:
            signal: Trading signal with entry price and direction.
            account: Current account state with equity and positions.
            snapshot: Current market indicators including ATR.

        Returns:
            PositionSizing with quantity, stop loss, and take profit levels.
            None if the trade should be rejected due to risk constraints.
        """
        try:
            return self._calculate_sizing(signal, account, snapshot)
        except Exception as e:
            self._logger.error(
                f"Risk calculation failed for signal {signal.signal_id}: {e}"
            )
            return None

    def _calculate_sizing(
        self,
        signal: TradingSignal,
        account: AccountState,
        snapshot: IndicatorSnapshot,
    ) -> PositionSizing | None:
        """Internal position sizing calculation.

        Args:
            signal: Trading signal to size.
            account: Current account state.
            snapshot: Current market snapshot.

        Returns:
            PositionSizing object or None if trade should be rejected.
        """
        # Calculate risk amount
        risk_amount = account.equity * self.config.risk_per_trade

        # Validate minimum risk amount
        if risk_amount < 1.0:  # Minimum $1 risk
            self._logger.warning(f"Risk amount too small: ${risk_amount:.2f}")
            return None

        # Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_levels(signal, snapshot)

        if stop_loss is None:
            self._logger.warning("Unable to calculate stop loss level")
            return None

        # Calculate position size based on risk model
        if self.config.model == RiskModel.ATR:
            quantity = self._calculate_atr_size(signal, risk_amount, stop_loss)
        else:  # PERCENT model
            quantity = self._calculate_percent_size(signal, account, risk_amount)

        if quantity is None or abs(quantity) < self.config.min_position:
            self._logger.warning(f"Position size too small: {quantity}")
            return None

        # Validate position size limits
        position_value = abs(float(quantity)) * signal.entry_price
        max_position_value = account.equity * self.config.max_position_pct

        if position_value > max_position_value:
            # Scale down to maximum allowed position
            scale_factor = max_position_value / position_value
            quantity = Decimal(str(float(quantity) * scale_factor))
            self._logger.info(
                f"Position scaled down by {scale_factor:.2f} due to size limits"
            )

        # Calculate notional value
        notional = abs(float(quantity)) * signal.entry_price

        return PositionSizing(
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit or 0.0,  # Provide default if None
            direction=signal.direction,
            risk_amount=risk_amount,
            entry_price=signal.entry_price,
            notional=notional,
        )

    def _calculate_levels(
        self,
        signal: TradingSignal,
        snapshot: IndicatorSnapshot,
    ) -> tuple[float | None, float | None]:
        """Calculate stop loss and take profit levels.

        Args:
            signal: Trading signal with entry price and direction.
            snapshot: Current market snapshot with ATR.

        Returns:
            Tuple of (stop_loss, take_profit) prices.
        """
        if not snapshot.atr or snapshot.atr <= 0:
            return None, None

        atr_distance = snapshot.atr * self.config.sl_atr_multiple

        if signal.direction == SignalDirection.LONG:
            stop_loss = signal.entry_price - atr_distance
            take_profit = signal.entry_price + (atr_distance * self.config.tp_rr)
        else:  # SHORT
            stop_loss = signal.entry_price + atr_distance
            take_profit = signal.entry_price - (atr_distance * self.config.tp_rr)

        return stop_loss, take_profit

    def _calculate_atr_size(
        self,
        signal: TradingSignal,
        risk_amount: float,
        stop_loss: float,
    ) -> Decimal | None:
        """Calculate position size using ATR-based risk model.

        Args:
            signal: Trading signal.
            risk_amount: Dollar amount to risk.
            stop_loss: Stop loss price level.

        Returns:
            Position quantity or None if calculation fails.
        """
        # Calculate risk per unit
        risk_per_unit = abs(signal.entry_price - stop_loss)

        if risk_per_unit <= 0:
            return None

        # Calculate quantity: risk_amount / risk_per_unit
        quantity = risk_amount / risk_per_unit

        # Apply direction sign
        if signal.direction == SignalDirection.SHORT:
            quantity = -quantity

        return Decimal(str(quantity))

    def _calculate_percent_size(
        self,
        signal: TradingSignal,
        account: AccountState,
        risk_amount: float,
    ) -> Decimal | None:
        """Calculate position size using percentage-based risk model.

        Args:
            signal: Trading signal.
            account: Account state.
            risk_amount: Dollar amount to risk.

        Returns:
            Position quantity or None if calculation fails.
        """
        # For percentage model, use fixed percentage of available equity
        position_value = risk_amount * 10  # 10x leverage simulation
        quantity = position_value / signal.entry_price

        # Apply direction sign
        if signal.direction == SignalDirection.SHORT:
            quantity = -quantity

        return Decimal(str(quantity))

    def validate_signal(
        self,
        signal: TradingSignal,
        account: AccountState,
    ) -> bool:
        """Validate if a signal should be allowed to trade.

        Performs basic risk checks before position sizing calculations.

        Args:
            signal: Trading signal to validate.
            account: Current account state.

        Returns:
            True if signal passes risk validation, False otherwise.
        """
        # Check if we have sufficient equity
        min_equity = 100.0  # Minimum $100 account
        if account.equity < min_equity:
            self._logger.warning(f"Account equity too low: ${account.equity:.2f}")
            return False

        # Check if we already have a position in this symbol
        if signal.symbol in account.positions:
            existing_pos = account.positions[signal.symbol]
            # Don't allow opposing positions
            existing_direction = (
                SignalDirection.LONG
                if existing_pos.quantity > 0
                else SignalDirection.SHORT
            )
            if existing_direction != signal.direction:
                self._logger.warning(f"Opposing position exists for {signal.symbol}")
                return False

        return True
