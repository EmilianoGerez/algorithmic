from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from core.entities import Candle

__all__ = ["ATR", "ATRIndicator"]


@dataclass
class ATR:
    """Average True Range (ATR) indicator for volatility measurement.

    The ATR is a technical analysis indicator that measures market volatility by
    decomposing the entire range of an asset price for that period. It is calculated
    as the simple moving average of the True Range values over a specified period.

    True Range is defined as:
        max(high - low, abs(high - prev_close), abs(low - prev_close))

    Args:
        period: Number of periods to use for ATR calculation. Typically 14.

    Attributes:
        period: The period length for ATR calculation.

    Example:
        >>> atr = ATR(period=14)
        >>> atr.update(candle)
        >>> if atr.is_ready:
        ...     volatility = atr.value
    """

    period: int

    def __post_init__(self) -> None:
        self._true_ranges: deque[float] = deque(maxlen=self.period)
        self._prev_close: float | None = None
        self._atr_value: float | None = None

    def update(self, candle: Candle) -> None:
        """Update ATR with new candle data.

        Calculates the True Range for the current candle and updates the ATR
        using a simple moving average. The ATR value becomes available once
        enough candles have been processed (equal to the period).

        Args:
            candle: The new candle data containing OHLCV information.

        Note:
            For the first candle, True Range is simply high - low since no
            previous close is available.
        """
        # Calculate True Range
        if self._prev_close is None:
            # First candle - only high-low range available
            true_range = candle.high - candle.low
        else:
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - self._prev_close),
                abs(candle.low - self._prev_close),
            )

        self._true_ranges.append(true_range)
        self._prev_close = candle.close

        # Calculate ATR (SMA of True Ranges)
        if len(self._true_ranges) == self.period:
            raw_atr = sum(self._true_ranges) / self.period
            # Apply ATR floor to prevent micro-ATR issues with identical OHLC bars
            # Use a minimal tick size (0.00001 for crypto, 0.0001 for forex)
            atr_floor = 0.00001  # Configurable tick size
            self._atr_value = max(raw_atr, atr_floor)
        else:
            # Not enough data yet
            self._atr_value = None

    @property
    def value(self) -> float | None:
        """Current ATR value.

        Returns:
            The current ATR value if enough data is available, None otherwise.
            ATR represents the average volatility over the specified period.
        """
        return self._atr_value

    @property
    def is_ready(self) -> bool:
        """Check if ATR has sufficient data to produce valid values.

        Returns:
            True if ATR has processed enough candles (equal to period),
            False otherwise.
        """
        return len(self._true_ranges) == self.period


# Alias for backwards compatibility
ATRIndicator = ATR
