from __future__ import annotations

from dataclasses import dataclass

from core.entities import Candle
from core.indicators.atr import ATR
from core.indicators.ema import EMA
from core.indicators.regime import RegimeDetector
from core.indicators.snapshot import IndicatorSnapshot
from core.indicators.volume_sma import VolumeSMA

__all__ = ["IndicatorPack"]


@dataclass
class IndicatorPack:
    """Central coordinator for all technical indicators.

    Manages a suite of technical indicators and provides a unified interface
    for updates and state capture. Ensures all indicators stay synchronized
    and provides immutable snapshots for decision making.

    The pack includes:
        - EMA21 and EMA50 for trend analysis
        - ATR for volatility measurement
        - Volume SMA for volume analysis
        - Regime detector for market classification

    Args:
        ema21_period: Period for fast EMA. Default 21.
        ema50_period: Period for slow EMA. Default 50.
        atr_period: Period for ATR calculation. Default 14.
        volume_sma_period: Period for volume averaging. Default 20.
        regime_sensitivity: Slope filter threshold for regime detection. Default 0.001.

    Example:
        >>> pack = IndicatorPack()
        >>> pack.update(candle)
        >>> if pack.is_ready:
        ...     snapshot = pack.snapshot()
        ...     if snapshot.regime.is_bullish:
        ...         # Process bullish signal
    """

    ema21_period: int = 21
    ema50_period: int = 50
    atr_period: int = 14
    volume_sma_period: int = 20
    regime_sensitivity: float = 0.001

    def __post_init__(self) -> None:
        # Initialize all indicators
        self.ema21 = EMA(self.ema21_period)
        self.ema50 = EMA(self.ema50_period)
        self.atr = ATR(self.atr_period)
        self.volume_sma = VolumeSMA(self.volume_sma_period)
        self.regime_detector = RegimeDetector(self.regime_sensitivity)

        # Track last candle for snapshot
        self._last_candle: Candle | None = None

    def update(self, candle: Candle) -> None:
        """Update all indicators with new candle data.

        Synchronously updates all indicators maintaining consistency across
        the indicator suite. This is the primary method for feeding new data.

        Args:
            candle: New candle data containing OHLCV information.

        Note:
            Call this once per candle to maintain synchronization across
            all indicators in the pack.
        """
        # Update all indicators
        self.ema21.update(candle)
        self.ema50.update(candle)
        self.atr.update(candle)
        self.volume_sma.update(candle)
        self.regime_detector.update(candle, self.atr.value)

        # Store candle for snapshot
        self._last_candle = candle

    def snapshot(self) -> IndicatorSnapshot:
        """Create immutable snapshot of current indicator state.

        Captures the state of all indicators AFTER updating with the current
        candle. This ensures no look-ahead bias in decision making algorithms.

        Returns:
            Immutable snapshot containing all indicator values and derived
            properties at the current timestamp.

        Raises:
            ValueError: If called before any candle has been processed.

        Example:
            >>> pack.update(candle)
            >>> snapshot = pack.snapshot()
            >>> if snapshot.is_ready and snapshot.regime.is_bullish:
            ...     # All indicators ready and regime is bullish
        """
        if self._last_candle is None:
            raise ValueError("Cannot create snapshot before updating with any candle")

        return IndicatorSnapshot(
            timestamp=self._last_candle.ts,
            ema21=self.ema21.value,
            ema50=self.ema50.value,
            atr=self.atr.value,
            volume_sma=self.volume_sma.value,
            regime=self.regime_detector.regime,
            regime_with_slope=self.regime_detector.regime_with_slope_filter(
                self.atr.value
            ),
            current_volume=self._last_candle.volume,
            current_close=self._last_candle.close,
        )

    @property
    def is_ready(self) -> bool:
        """True if all indicators have sufficient data."""
        return all(
            [
                self.ema21.value is not None,
                self.ema50.value is not None,
                self.atr.is_ready,
                self.volume_sma.is_ready,
            ]
        )

    @property
    def warmup_periods_needed(self) -> int:
        """Maximum warmup period needed across all indicators."""
        return max(
            self.ema21_period,
            self.ema50_period,
            self.atr_period,
            self.volume_sma_period,
        )
