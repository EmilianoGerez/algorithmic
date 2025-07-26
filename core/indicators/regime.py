from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.entities import Candle
from core.indicators.ema import EMA

__all__ = ["Regime", "RegimeDetector"]


class Regime(Enum):
    """Market regime classification for trend analysis.

    Used to classify market conditions based on EMA alignment and trend strength.
    Provides ergonomic comparison methods for strategy filtering.
    """

    BULL = 1
    BEAR = -1
    NEUTRAL = 0

    @property
    def is_bullish(self) -> bool:
        """True if regime is bullish."""
        return self == Regime.BULL

    @property
    def is_bearish(self) -> bool:
        """True if regime is bearish."""
        return self == Regime.BEAR

    @property
    def is_neutral(self) -> bool:
        """True if regime is neutral."""
        return self == Regime.NEUTRAL

    @property
    def is_trending(self) -> bool:
        """True if regime is either bullish or bearish (not neutral)."""
        return self in (Regime.BULL, Regime.BEAR)


@dataclass
class RegimeDetector:
    """Market regime classification based on EMA alignment with optional slope filter.

    Classifies market conditions into BULL, BEAR, or NEUTRAL states based on the
    relationship between fast and slow EMAs. An optional slope filter helps avoid
    whipsaw signals during sideways markets.

    Classification Logic:
        - EMA21 > EMA50 → BULL (if slope filter passes)
        - EMA21 < EMA50 → BEAR (if slope filter passes)
        - Otherwise → NEUTRAL

    Slope Filter:
        When enabled, requires (EMA21 - EMA50) / ATR > sensitivity threshold
        to avoid classifying minor EMA crossovers as regime changes.

    Args:
        sensitivity: Slope filter threshold. Higher values require stronger
                    trends to classify as BULL/BEAR. Default 0.001.

    Example:
        >>> detector = RegimeDetector(sensitivity=0.002)
        >>> detector.update(candle, atr_value)
        >>> if detector.regime and detector.regime.is_bullish:
        ...     # Handle bullish regime
    """

    sensitivity: float = 0.001

    def __post_init__(self) -> None:
        self._ema21 = EMA(21)
        self._ema50 = EMA(50)
        self._prev_ema21: float | None = None
        self._prev_ema50: float | None = None

    def update(self, candle: Candle, atr_value: float | None = None) -> None:
        """Update regime classification with new candle data.

        Updates the internal EMAs and prepares for regime classification.
        The ATR value is stored for potential use in slope filtering.

        Args:
            candle: New candle data containing OHLCV information.
            atr_value: Current ATR value for slope filtering. Optional.
        """
        self._ema21.update(candle)
        self._ema50.update(candle)

    @property
    def regime(self) -> Regime | None:
        """Current market regime without slope filtering.

        Returns:
            Current regime classification (BULL/BEAR/NEUTRAL) or None
            if insufficient EMA data is available.
        """
        ema21_val = self._ema21.value
        ema50_val = self._ema50.value

        if ema21_val is None or ema50_val is None:
            return None

        # Basic regime without slope filter
        if ema21_val > ema50_val:
            return Regime.BULL
        elif ema21_val < ema50_val:
            return Regime.BEAR
        else:
            return Regime.NEUTRAL

    def regime_with_slope_filter(self, atr_value: float | None) -> Regime | None:
        """Regime classification with slope filter to avoid whipsaws.

        Applies a slope filter that requires the EMA difference to exceed
        a threshold relative to ATR before classifying as trending.

        Args:
            atr_value: Current ATR value for slope strength calculation.
                      If None, basic regime logic is applied.

        Returns:
            Regime classification with slope filter applied, or None
            if insufficient data.
        """
        ema21_val = self._ema21.value
        ema50_val = self._ema50.value

        if ema21_val is None or ema50_val is None:
            return None

        # If we have ATR, apply slope filter
        if atr_value is not None and atr_value > 0:
            ema_diff = ema21_val - ema50_val
            slope_strength = abs(ema_diff) / atr_value

            if slope_strength < self.sensitivity:
                return Regime.NEUTRAL

        # Apply basic regime logic
        if ema21_val > ema50_val:
            return Regime.BULL
        elif ema21_val < ema50_val:
            return Regime.BEAR
        else:
            return Regime.NEUTRAL

    @property
    def ema21_value(self) -> float | None:
        return self._ema21.value

    @property
    def ema50_value(self) -> float | None:
        return self._ema50.value
