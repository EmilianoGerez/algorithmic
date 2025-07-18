"""
FVG Detector

Fair Value Gap detection algorithm extracted from the proven legacy system.
Clean implementation with enhanced filtering and quality scoring.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from ..data.models import Candle, FVGZone, SignalDirection, TimeFrame


class FVGQuality(Enum):
    """FVG Quality levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PREMIUM = "premium"


@dataclass
class FVGFilterConfig:
    """Configuration for FVG filtering parameters"""
    # Zone size filters
    min_zone_size_pips: float = 5.0
    min_zone_size_percentage: float = 0.02  # 2% of price
    min_zone_size_atr_multiplier: float = 0.3
    
    # Volume filters
    min_volume_multiplier: float = 1.2
    volume_context_periods: int = 20
    
    # Context filters
    min_strength_threshold: float = 0.6
    exclude_weekend_fvgs: bool = True
    max_age_hours: int = 168  # 1 week
    
    # Market context filters
    avoid_consolidation_fvgs: bool = True
    min_momentum_threshold: float = 0.5
    
    # Quality thresholds
    high_quality_threshold: float = 0.7
    premium_quality_threshold: float = 0.85


class FVGDetector:
    """
    Fair Value Gap detector with enhanced filtering and quality scoring.
    
    Based on the proven logic from the legacy system with improvements:
    - Clean, decoupled implementation
    - Enhanced quality scoring
    - Configurable filtering
    - Better performance
    """
    
    def __init__(self, config: Optional[FVGFilterConfig] = None):
        """
        Initialize FVG detector.
        
        Args:
            config: FVG filter configuration
        """
        self.config = config or FVGFilterConfig()
        self.detected_fvgs: List[FVGZone] = []
    
    def detect_fvgs(self, candles: List[Candle]) -> List[FVGZone]:
        """
        Detect Fair Value Gaps in price data.
        
        Args:
            candles: List of candles to analyze
            
        Returns:
            List of detected FVG zones
        """
        if len(candles) < 3:
            return []
        
        fvg_zones = []
        atr = self._calculate_atr(candles)
        
        for i in range(1, len(candles) - 1):
            prev_candle = candles[i - 1]
            current_candle = candles[i]
            next_candle = candles[i + 1]
            
            # Check for bullish FVG: previous high < next low
            if prev_candle.high < next_candle.low:
                fvg_zone = self._create_fvg_zone(
                    candles, i, prev_candle.high, next_candle.low, 
                    SignalDirection.LONG, atr
                )
                if fvg_zone:
                    fvg_zones.append(fvg_zone)
            
            # Check for bearish FVG: previous low > next high
            elif prev_candle.low > next_candle.high:
                fvg_zone = self._create_fvg_zone(
                    candles, i, next_candle.high, prev_candle.low,
                    SignalDirection.SHORT, atr
                )
                if fvg_zone:
                    fvg_zones.append(fvg_zone)
        
        self.detected_fvgs = fvg_zones
        return fvg_zones
    
    def _create_fvg_zone(
        self, 
        candles: List[Candle], 
        index: int, 
        zone_low: Decimal, 
        zone_high: Decimal,
        direction: SignalDirection,
        atr: float
    ) -> Optional[FVGZone]:
        """
        Create and validate an FVG zone.
        
        Args:
            candles: List of candles
            index: Index of the gap candle
            zone_low: Lower bound of the zone
            zone_high: Upper bound of the zone
            direction: FVG direction
            atr: Average True Range
            
        Returns:
            FVG zone if valid, None otherwise
        """
        current_candle = candles[index]
        zone_size = float(zone_high - zone_low)
        
        # Validate zone size
        if not self._is_zone_size_valid(zone_size, float(current_candle.close), atr):
            return None
        
        # Calculate strength and confidence
        strength = self._calculate_fvg_strength(candles, index, zone_size, atr)
        confidence = self._calculate_fvg_confidence(candles, index, strength)
        
        # Apply quality filters
        if strength < self.config.min_strength_threshold:
            return None
        
        if not self._passes_context_filters(candles, index):
            return None
        
        return FVGZone(
            timestamp=current_candle.timestamp,
            symbol=current_candle.symbol,
            timeframe=current_candle.timeframe,
            direction=direction,
            zone_high=zone_high,
            zone_low=zone_low,
            strength=strength,
            confidence=confidence,
            status="active",
            created_candle_index=index,
            metadata={
                "atr": atr,
                "zone_size": zone_size,
                "quality": self._get_quality_level(strength, confidence)
            }
        )
    
    def _is_zone_size_valid(self, zone_size: float, price: float, atr: float) -> bool:
        """Check if zone size meets minimum requirements"""
        # Minimum pips
        if zone_size < self.config.min_zone_size_pips:
            return False
        
        # Minimum percentage of price
        if (zone_size / price) < self.config.min_zone_size_percentage:
            return False
        
        # Minimum ATR multiplier
        if atr > 0 and zone_size < (atr * self.config.min_zone_size_atr_multiplier):
            return False
        
        return True
    
    def _calculate_fvg_strength(
        self, 
        candles: List[Candle], 
        index: int, 
        zone_size: float, 
        atr: float
    ) -> float:
        """
        Calculate FVG strength score (0.0 to 1.0).
        
        Factors:
        - Zone size relative to ATR
        - Volume strength
        - Momentum
        - Market structure context
        """
        strength = 0.5  # Base strength
        
        # Factor 1: Zone size relative to ATR
        if atr > 0:
            atr_factor = min(zone_size / atr, 3.0) / 3.0
            strength += atr_factor * 0.25
        
        # Factor 2: Volume strength
        volume_factor = self._calculate_volume_factor(candles, index)
        strength += volume_factor * 0.2
        
        # Factor 3: Momentum strength
        momentum_factor = self._calculate_momentum_factor(candles, index)
        strength += momentum_factor * 0.15
        
        # Factor 4: Market structure context
        if not self._is_in_consolidation(candles, index):
            strength += 0.1  # Bonus for trending market
        
        return min(strength, 1.0)
    
    def _calculate_fvg_confidence(self, candles: List[Candle], index: int, strength: float) -> float:
        """
        Calculate FVG confidence score (0.0 to 1.0).
        
        Based on:
        - Strength score
        - Market context
        - Historical performance patterns
        """
        confidence = strength * 0.7  # Base confidence from strength
        
        # Context bonus
        if not self._is_in_consolidation(candles, index):
            confidence += 0.15
        
        # Volume confirmation
        if self._has_sufficient_volume(candles, index):
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def _calculate_volume_factor(self, candles: List[Candle], index: int) -> float:
        """Calculate volume factor for strength calculation"""
        if index < self.config.volume_context_periods:
            return 0.0
        
        current_volume = float(candles[index].volume)
        if current_volume == 0:
            return 0.0
        
        # Calculate average volume
        context_start = max(0, index - self.config.volume_context_periods)
        context_candles = candles[context_start:index]
        
        if not context_candles:
            return 0.0
        
        avg_volume = sum(float(c.volume) for c in context_candles) / len(context_candles)
        
        if avg_volume == 0:
            return 0.0
        
        volume_ratio = current_volume / avg_volume
        return min(volume_ratio / 2.0, 1.0)  # Normalize to 0-1
    
    def _calculate_momentum_factor(self, candles: List[Candle], index: int) -> float:
        """Calculate momentum factor for strength calculation"""
        if index < 10:
            return 0.0
        
        current_close = float(candles[index].close)
        past_close = float(candles[index - 10].close)
        
        if past_close == 0:
            return 0.0
        
        momentum = abs(current_close - past_close) / past_close
        return min(momentum, 1.0)
    
    def _is_in_consolidation(self, candles: List[Candle], index: int, period: int = 20) -> bool:
        """Check if price is in consolidation phase"""
        if index < period:
            return False
        
        context_start = max(0, index - period)
        context_candles = candles[context_start:index + 1]
        
        high_prices = [float(c.high) for c in context_candles]
        low_prices = [float(c.low) for c in context_candles]
        
        price_range = max(high_prices) - min(low_prices)
        avg_price = sum(float(c.close) for c in context_candles) / len(context_candles)
        
        return (price_range / avg_price) < 0.02  # 2% range threshold
    
    def _has_sufficient_volume(self, candles: List[Candle], index: int) -> bool:
        """Check if candle has sufficient volume"""
        if index < self.config.volume_context_periods:
            return True
        
        current_volume = float(candles[index].volume)
        if current_volume == 0:
            return False
        
        # Calculate average volume
        context_start = max(0, index - self.config.volume_context_periods)
        context_candles = candles[context_start:index]
        
        if not context_candles:
            return True
        
        avg_volume = sum(float(c.volume) for c in context_candles) / len(context_candles)
        
        if avg_volume == 0:
            return True
        
        return current_volume >= (avg_volume * self.config.min_volume_multiplier)
    
    def _passes_context_filters(self, candles: List[Candle], index: int) -> bool:
        """Check if FVG passes context filters"""
        # Weekend filter
        if self.config.exclude_weekend_fvgs:
            if candles[index].timestamp.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return False
        
        # Consolidation filter
        if self.config.avoid_consolidation_fvgs:
            if self._is_in_consolidation(candles, index):
                return False
        
        # Momentum filter
        momentum = self._calculate_momentum_factor(candles, index)
        if momentum < self.config.min_momentum_threshold:
            return False
        
        return True
    
    def _calculate_atr(self, candles: List[Candle], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(candles) < period:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(candles)):
            current = candles[i]
            previous = candles[i - 1]
            
            tr = max(
                float(current.high - current.low),
                abs(float(current.high - previous.close)),
                abs(float(current.low - previous.close))
            )
            true_ranges.append(tr)
        
        # Return average of the last 'period' true ranges
        recent_trs = true_ranges[-period:]
        return sum(recent_trs) / len(recent_trs)
    
    def _get_quality_level(self, strength: float, confidence: float) -> FVGQuality:
        """Determine quality level based on strength and confidence"""
        combined_score = (strength + confidence) / 2
        
        if combined_score >= self.config.premium_quality_threshold:
            return FVGQuality.PREMIUM
        elif combined_score >= self.config.high_quality_threshold:
            return FVGQuality.HIGH
        elif combined_score >= 0.5:
            return FVGQuality.MEDIUM
        else:
            return FVGQuality.LOW
    
    def get_active_fvgs(self) -> List[FVGZone]:
        """Get currently active FVG zones"""
        return [fvg for fvg in self.detected_fvgs if fvg.status == "active"]
    
    def update_fvg_status(self, fvg_zone: FVGZone, new_price: Decimal) -> None:
        """Update FVG status based on price interaction"""
        if fvg_zone.is_price_in_zone(new_price):
            fvg_zone.touch_count += 1
            fvg_zone.status = "touched"
        
        # Invalidation logic can be added here
        # e.g., if price moves significantly beyond the zone
    
    def get_quality_metrics(self) -> Dict[str, float]:
        """Get quality metrics for detected FVGs"""
        if not self.detected_fvgs:
            return {}
        
        total_fvgs = len(self.detected_fvgs)
        high_quality_count = sum(
            1 for fvg in self.detected_fvgs 
            if fvg.strength >= self.config.high_quality_threshold
        )
        
        avg_strength = sum(fvg.strength for fvg in self.detected_fvgs) / total_fvgs
        avg_confidence = sum(fvg.confidence for fvg in self.detected_fvgs) / total_fvgs
        
        return {
            "total_fvgs": total_fvgs,
            "high_quality_count": high_quality_count,
            "quality_rate": high_quality_count / total_fvgs,
            "average_strength": avg_strength,
            "average_confidence": avg_confidence
        }


class FVGFilterPresets:
    """Predefined filter configurations for different trading styles"""
    
    @staticmethod
    def conservative() -> FVGFilterConfig:
        """Conservative filtering - only highest quality FVGs"""
        return FVGFilterConfig(
            min_zone_size_pips=10.0,
            min_zone_size_percentage=0.03,
            min_zone_size_atr_multiplier=0.5,
            min_volume_multiplier=1.5,
            min_strength_threshold=0.7,
            min_momentum_threshold=0.7,
            high_quality_threshold=0.8,
            premium_quality_threshold=0.9
        )
    
    @staticmethod
    def balanced() -> FVGFilterConfig:
        """Balanced filtering - default settings"""
        return FVGFilterConfig()
    
    @staticmethod
    def aggressive() -> FVGFilterConfig:
        """Aggressive filtering - more FVGs, lower quality threshold"""
        return FVGFilterConfig(
            min_zone_size_pips=3.0,
            min_zone_size_percentage=0.01,
            min_zone_size_atr_multiplier=0.2,
            min_volume_multiplier=1.0,
            min_strength_threshold=0.5,
            min_momentum_threshold=0.3,
            high_quality_threshold=0.6,
            premium_quality_threshold=0.75
        )
    
    @staticmethod
    def scalping() -> FVGFilterConfig:
        """Scalping filtering - very tight filters for quick trades"""
        return FVGFilterConfig(
            min_zone_size_pips=2.0,
            min_zone_size_percentage=0.005,
            min_zone_size_atr_multiplier=0.1,
            min_volume_multiplier=1.8,
            min_strength_threshold=0.8,
            min_momentum_threshold=0.8,
            high_quality_threshold=0.85,
            premium_quality_threshold=0.95,
            avoid_consolidation_fvgs=True
        )
