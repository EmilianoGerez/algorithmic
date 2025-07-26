"""
Risk management configuration and settings.

This module defines the configuration structure for risk management parameters
including position sizing models, risk limits, and stop/take profit calculations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = ["RiskModel", "RiskConfig"]


class RiskModel(str, Enum):
    """Position sizing risk models."""

    ATR = "atr"
    PERCENT = "percent"


@dataclass(slots=True, frozen=True)
class RiskConfig:
    """Risk management configuration parameters.

    Defines all parameters needed for position sizing calculations and
    risk management decisions. This configuration determines how much
    capital to risk per trade and how to calculate stop losses and
    take profits.

    Attributes:
        model: Risk model to use (ATR-based or percentage-based)
        risk_per_trade: Maximum fraction of account to risk per trade (0.01 = 1%)
        atr_period: ATR period for volatility calculations (typically 14)
        sl_atr_multiple: Stop loss distance as multiple of ATR (e.g., 1.5 * ATR)
        tp_rr: Take profit ratio relative to risk (e.g., 2.0 = 2:1 reward:risk)
        min_position: Minimum position size (useful for futures contracts)
        max_position_pct: Maximum position size as percentage of account
        max_correlation: Maximum correlation between open positions (future use)
        slippage_fn: Optional slippage model function(price, qty) -> slipped_price
    """

    model: RiskModel = RiskModel.ATR
    risk_per_trade: float = 0.01  # 1% of account
    atr_period: int = 14
    sl_atr_multiple: float = 1.5
    tp_rr: float = 2.0  # 2:1 reward to risk ratio
    min_position: float = 0.01  # Minimum position size
    max_position_pct: float = 0.1  # Max 10% of account in single position
    max_correlation: float = 0.7  # Future use for position correlation limits
    slippage_fn: Callable[[float, float], float] | None = (
        None  # (price, qty) -> slipped_price
    )

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if not 0 < self.risk_per_trade <= 0.1:
            raise ValueError(
                f"risk_per_trade must be between 0 and 0.1, got {self.risk_per_trade}"
            )

        if self.atr_period < 1:
            raise ValueError(f"atr_period must be positive, got {self.atr_period}")

        if self.sl_atr_multiple <= 0:
            raise ValueError(
                f"sl_atr_multiple must be positive, got {self.sl_atr_multiple}"
            )

        if self.tp_rr <= 0:
            raise ValueError(f"tp_rr must be positive, got {self.tp_rr}")

        if not 0 < self.max_position_pct <= 1.0:
            raise ValueError(
                f"max_position_pct must be between 0 and 1, got {self.max_position_pct}"
            )
