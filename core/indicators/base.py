from __future__ import annotations

from typing import Optional, Protocol

from core.entities import Candle


class Indicator(Protocol):
    def update(self, candle: Candle) -> None: ...
    @property
    def value(self) -> float | None: ...


class IndicatorPack:
    """Container for multiple indicators with snapshot capability."""

    def __init__(self) -> None:
        """Initialize indicator pack."""
        from core.indicators.atr import ATR
        from core.indicators.ema import EMA
        from core.indicators.volume_sma import VolumeSMA

        self.ema21 = EMA(21)
        self.ema50 = EMA(50)
        self.atr = ATR(14)  # Standard 14-period ATR
        self.volume_sma = VolumeSMA(20)  # 20-period volume SMA

    def update(self, candle: Candle) -> None:
        """Update all indicators with new candle.

        Args:
            candle: Market data candle
        """
        self.ema21.update(candle)
        self.ema50.update(candle)
        self.atr.update(candle)
        self.volume_sma.update(candle)

    @property
    def ema21_value(self) -> float | None:
        """Get EMA21 value."""
        return self.ema21.value

    @property
    def ema50_value(self) -> float | None:
        """Get EMA50 value."""
        return self.ema50.value

    @property
    def atr_value(self) -> float | None:
        """Get ATR value."""
        return self.atr.value

    @property
    def volume_sma_value(self) -> float | None:
        """Get Volume SMA value."""
        return self.volume_sma.value
