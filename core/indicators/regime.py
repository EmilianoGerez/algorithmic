from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from core.entities import Candle
from core.indicators.ema import EMA

__all__ = ["Regime", "RegimeDetector"]


class Regime(Enum):
    BULL = 1
    BEAR = -1
    NEUTRAL = 0


@dataclass
class RegimeDetector:
    """
    Market regime classification based on EMA alignment with optional slope filter.
    
    Logic:
    - EMA21 > EMA50 → BULL (if slope filter passes)
    - EMA21 < EMA50 → BEAR (if slope filter passes)  
    - Otherwise → NEUTRAL
    
    Slope filter: (EMA21 - EMA50) / ATR > sensitivity threshold
    """
    sensitivity: float = 0.001
    
    def __post_init__(self):
        self._ema21 = EMA(21)
        self._ema50 = EMA(50)
        self._prev_ema21: Optional[float] = None
        self._prev_ema50: Optional[float] = None

    def update(self, candle: Candle, atr_value: Optional[float] = None) -> None:
        """Update regime with new candle. ATR value used for slope filter."""
        self._ema21.update(candle)
        self._ema50.update(candle)

    @property
    def regime(self) -> Optional[Regime]:
        """Current market regime, None if insufficient data."""
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

    def regime_with_slope_filter(self, atr_value: Optional[float]) -> Optional[Regime]:
        """Regime with slope filter applied to avoid whipsaws."""
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
    def ema21_value(self) -> Optional[float]:
        return self._ema21.value
        
    @property  
    def ema50_value(self) -> Optional[float]:
        return self._ema50.value
