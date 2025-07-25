from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from core.entities import Candle
from core.indicators.ema import EMA
from core.indicators.atr import ATR
from core.indicators.volume_sma import VolumeSMA
from core.indicators.regime import RegimeDetector
from core.indicators.snapshot import IndicatorSnapshot

__all__ = ["IndicatorPack"]


@dataclass
class IndicatorPack:
    """
    Central coordinator for all indicators.
    
    Single update() call updates all indicators.
    snapshot() returns immutable state for decision making.
    """
    ema21_period: int = 21
    ema50_period: int = 50
    atr_period: int = 14
    volume_sma_period: int = 20
    regime_sensitivity: float = 0.001
    
    def __post_init__(self):
        # Initialize all indicators
        self.ema21 = EMA(self.ema21_period)
        self.ema50 = EMA(self.ema50_period)
        self.atr = ATR(self.atr_period)
        self.volume_sma = VolumeSMA(self.volume_sma_period)
        self.regime_detector = RegimeDetector(self.regime_sensitivity)
        
        # Track last candle for snapshot
        self._last_candle: Optional[Candle] = None

    def update(self, candle: Candle) -> None:
        """
        Update all indicators with new candle.
        
        Call this once per candle to maintain sync across all indicators.
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
        """
        Create immutable snapshot of current indicator state.
        
        Captures state AFTER updating with current candle.
        Safe from look-ahead bias.
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
            regime_with_slope=self.regime_detector.regime_with_slope_filter(self.atr.value),
            current_volume=self._last_candle.volume,
            current_close=self._last_candle.close
        )
    
    @property
    def is_ready(self) -> bool:
        """True if all indicators have sufficient data."""
        return all([
            self.ema21.value is not None,
            self.ema50.value is not None,
            self.atr.is_ready,
            self.volume_sma.is_ready
        ])
    
    @property
    def warmup_periods_needed(self) -> int:
        """Maximum warmup period needed across all indicators."""
        return max(
            self.ema21_period,
            self.ema50_period, 
            self.atr_period,
            self.volume_sma_period
        )
