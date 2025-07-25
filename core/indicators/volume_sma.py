from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Deque
from collections import deque

from core.entities import Candle

__all__ = ["VolumeSMA"]


@dataclass
class VolumeSMA:
    """
    Simple Moving Average of volume over specified period.
    
    Used for detecting volume surges and regime changes.
    """
    period: int
    
    def __post_init__(self):
        self._volumes: Deque[float] = deque(maxlen=self.period)
        self._sma_value: Optional[float] = None

    def update(self, candle: Candle) -> None:
        """Update Volume SMA with new candle."""
        self._volumes.append(candle.volume)
        
        # Calculate SMA
        if len(self._volumes) == self.period:
            self._sma_value = sum(self._volumes) / self.period
        else:
            # Not enough data yet
            self._sma_value = None

    @property
    def value(self) -> Optional[float]:
        """Current Volume SMA value, None if insufficient data."""
        return self._sma_value

    @property
    def is_ready(self) -> bool:
        """True if Volume SMA has enough data to produce valid values."""
        return len(self._volumes) == self.period
        
    def volume_multiple(self, current_volume: float) -> Optional[float]:
        """
        Calculate volume multiple vs average.
        
        Returns:
            Multiple of current volume vs SMA (e.g. 2.5 = 250% of average)
            None if SMA not ready
        """
        if self._sma_value is None or self._sma_value == 0:
            return None
        return current_volume / self._sma_value
