from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.indicators.regime import Regime

__all__ = ["IndicatorSnapshot"]


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    """
    Immutable snapshot of all indicator values at a specific point in time.

    Used by FSM and decision logic to ensure no look-ahead bias.
    All values captured AFTER updating indicators with current candle.
    """
    timestamp: datetime
    ema21: float | None
    ema50: float | None
    atr: float | None
    volume_sma: float | None
    regime: Regime | None
    regime_with_slope: Regime | None
    current_volume: float
    current_close: float

    @property
    def is_ready(self) -> bool:
        """True if all core indicators have valid values."""
        return all([
            self.ema21 is not None,
            self.ema50 is not None,
            self.atr is not None,
            self.volume_sma is not None,
            self.regime is not None
        ])

    @property
    def ema_aligned_bullish(self) -> bool:
        """True if EMA21 > EMA50 (bullish alignment)."""
        if self.ema21 is None or self.ema50 is None:
            return False
        return self.ema21 > self.ema50

    @property
    def ema_aligned_bearish(self) -> bool:
        """True if EMA21 < EMA50 (bearish alignment)."""
        if self.ema21 is None or self.ema50 is None:
            return False
        return self.ema21 < self.ema50

    @property
    def volume_multiple(self) -> float | None:
        """Current volume as multiple of average volume."""
        if self.volume_sma is None or self.volume_sma == 0:
            return None
        return self.current_volume / self.volume_sma

    def volume_surge(self, threshold: float = 1.5) -> bool:
        """True if current volume exceeds threshold multiple of average."""
        vol_mult = self.volume_multiple
        return vol_mult is not None and vol_mult >= threshold
