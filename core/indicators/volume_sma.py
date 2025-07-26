from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from core.entities import Candle

__all__ = ["VolumeSMA", "VolumeSMAIndicator"]


@dataclass
class VolumeSMA:
    """Simple Moving Average of volume for volume analysis.

    Tracks average volume over a specified period to identify volume surges
    and changes in market participation. Used for regime detection and
    signal filtering.

    Args:
        period: Number of periods for volume averaging. Typically 20.

    Example:
        >>> vol_sma = VolumeSMA(period=20)
        >>> vol_sma.update(candle)
        >>> if vol_sma.is_ready:
        ...     surge = vol_sma.volume_multiple(current_volume) > 2.0
    """

    period: int

    def __post_init__(self) -> None:
        self._volumes: deque[float] = deque(maxlen=self.period)
        self._sma_value: float | None = None

    def update(self, candle: Candle) -> None:
        """Update Volume SMA with new candle data.

        Args:
            candle: New candle containing volume information.
        """
        self._volumes.append(candle.volume)

        # Calculate SMA
        if len(self._volumes) == self.period:
            self._sma_value = sum(self._volumes) / self.period
        else:
            # Not enough data yet
            self._sma_value = None

    @property
    def value(self) -> float | None:
        """Current Volume SMA value, None if insufficient data."""
        return self._sma_value

    @property
    def is_ready(self) -> bool:
        """True if Volume SMA has enough data to produce valid values."""
        return len(self._volumes) == self.period

    def volume_multiple(self, current_volume: float) -> float | None:
        """Calculate volume multiple versus average volume.

        Compares current volume to the SMA to identify volume surges or lulls.

        Args:
            current_volume: Volume value to compare against average.

        Returns:
            Multiple of current volume vs SMA (e.g. 2.5 = 250% of average).
            None if SMA not ready or is zero.

        Example:
            >>> multiple = vol_sma.volume_multiple(3000)
            >>> if multiple and multiple > 2.0:
            ...     print("Volume surge detected!")
        """
        if self._sma_value is None or self._sma_value == 0:
            return None
        return current_volume / self._sma_value


# Alias for backwards compatibility
VolumeSMAIndicator = VolumeSMA
