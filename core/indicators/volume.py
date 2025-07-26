"""Volume-based indicators for quantitative trading analysis."""

from __future__ import annotations

from collections import deque

from core.entities import Candle

__all__ = ["VolumeSMA", "VolumeSMAIndicator"]


class VolumeSMA:
    """Simple Moving Average of Volume indicator.

    Calculates the simple moving average of volume over a specified period.
    Used to identify above/below average volume conditions.

    Args:
        period: Number of periods to use for volume SMA calculation.

    Attributes:
        period: The period length for volume SMA calculation.

    Example:
        >>> vol_sma = VolumeSMA(period=20)
        >>> vol_sma.update(candle)
        >>> if vol_sma.is_ready:
        ...     avg_volume = vol_sma.value
        ...     is_high_volume = candle.volume > avg_volume * 1.5
    """

    def __init__(self, period: int) -> None:
        self.period = period
        self._volumes: deque[float] = deque(maxlen=period)
        self._sma_value: float | None = None

    def update(self, candle: Candle) -> None:
        """Update volume SMA with new candle data.

        Args:
            candle: The new candle data containing volume information.
        """
        self._volumes.append(candle.volume)

        if len(self._volumes) == self.period:
            self._sma_value = sum(self._volumes) / self.period
        else:
            self._sma_value = None

    @property
    def value(self) -> float | None:
        """Current volume SMA value.

        Returns:
            The current volume SMA value if enough data is available, None otherwise.
        """
        return self._sma_value

    @property
    def is_ready(self) -> bool:
        """Check if volume SMA has sufficient data to produce valid values.

        Returns:
            True if volume SMA has processed enough candles (equal to period),
            False otherwise.
        """
        return len(self._volumes) == self.period


# Alias for backwards compatibility
VolumeSMAIndicator = VolumeSMA
