from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Deque
from collections import deque

from core.entities import Candle

__all__ = ["ATR"]


@dataclass
class ATR:
    """
    Average True Range indicator.
    
    True Range = max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close)
    )
    
    ATR = Simple Moving Average of True Range over period.
    """
    period: int
    
    def __post_init__(self):
        self._true_ranges: Deque[float] = deque(maxlen=self.period)
        self._prev_close: Optional[float] = None
        self._atr_value: Optional[float] = None

    def update(self, candle: Candle) -> None:
        """Update ATR with new candle."""
        # Calculate True Range
        if self._prev_close is None:
            # First candle - only high-low range available
            true_range = candle.high - candle.low
        else:
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - self._prev_close),
                abs(candle.low - self._prev_close)
            )
        
        self._true_ranges.append(true_range)
        self._prev_close = candle.close
        
        # Calculate ATR (SMA of True Ranges)
        if len(self._true_ranges) == self.period:
            self._atr_value = sum(self._true_ranges) / self.period
        else:
            # Not enough data yet
            self._atr_value = None

    @property
    def value(self) -> Optional[float]:
        """Current ATR value, None if insufficient data."""
        return self._atr_value

    @property
    def is_ready(self) -> bool:
        """True if ATR has enough data to produce valid values."""
        return len(self._true_ranges) == self.period
