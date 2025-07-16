from typing import List, Dict, Optional
from datetime import datetime

class FVGFilterConfig:
    """Configuration for FVG filtering parameters"""
    def __init__(self):
        # Zone size filters
        self.min_zone_size_pips = 5.0  # Minimum zone size in pips
        self.min_zone_size_percentage = 0.02  # Minimum zone size as % of price (0.02 = 2%)
        self.min_zone_size_atr_multiplier = 0.3  # Minimum zone size as multiple of ATR
        
        # Volume filters
        self.min_volume_multiplier = 1.2  # Minimum volume vs recent average
        self.volume_context_periods = 20  # Periods to calculate volume average
        
        # Context filters
        self.min_strength_threshold = 0.6  # Minimum strength score
        self.exclude_weekend_fvgs = True  # Filter out weekend FVGs
        self.max_age_hours = 168  # Maximum age in hours (1 week)
        
        # Market context filters
        self.avoid_consolidation_fvgs = True  # Filter FVGs in consolidation
        self.min_momentum_threshold = 0.5  # Minimum momentum for FVG validity

def calculate_atr(candles: List[Dict], period: int = 14) -> float:
    """Calculate Average True Range for the given period"""
    if len(candles) < period:
        return 0.0
    
    true_ranges = []
    for i in range(1, len(candles)):
        current = candles[i]
        previous = candles[i-1]
        
        tr = max(
            current["high"] - current["low"],
            abs(current["high"] - previous["close"]),
            abs(current["low"] - previous["close"])
        )
        true_ranges.append(tr)
    
    # Return average of the last 'period' true ranges
    return sum(true_ranges[-period:]) / min(len(true_ranges), period)

def calculate_momentum(candles: List[Dict], period: int = 10) -> float:
    """Calculate momentum indicator"""
    if len(candles) < period:
        return 0.0
    
    current_close = candles[-1]["close"]
    past_close = candles[-period]["close"]
    
    return abs(current_close - past_close) / past_close

def is_in_consolidation(candles: List[Dict], period: int = 20, threshold: float = 0.02) -> bool:
    """Check if price is in consolidation phase"""
    if len(candles) < period:
        return False
    
    recent_candles = candles[-period:]
    high_prices = [c["high"] for c in recent_candles]
    low_prices = [c["low"] for c in recent_candles]
    
    price_range = max(high_prices) - min(low_prices)
    avg_price = sum(c["close"] for c in recent_candles) / len(recent_candles)
    
    return (price_range / avg_price) < threshold

def detect_fvg_with_filters(candles: List[Dict], config: FVGFilterConfig = None) -> List[Dict]:
    """
    Enhanced FVG detection with quality filters
    
    Args:
        candles: List of candle data
        config: FVG filter configuration
    
    Returns:
        List of filtered, high-quality FVG candles
    """
    if config is None:
        config = FVGFilterConfig()
    
    # First detect all FVGs using the original method
    result = []
    atr = calculate_atr(candles)
    
    for i in range(len(candles)):
        fvg_bullish = False
        fvg_bearish = False
        fvg_zone = None
        fvg_strength = 0.0
        
        if i >= 1 and i < len(candles) - 1:
            c_prev = candles[i - 1]
            c_current = candles[i]
            c_next = candles[i + 1]
            
            # Bullish FVG: previous high < next low
            if c_prev["high"] < c_next["low"]:
                fvg_zone = [c_prev["high"], c_next["low"]]
                zone_size = c_next["low"] - c_prev["high"]
                
                if _is_fvg_valid(c_current, fvg_zone, zone_size, candles, i, config, atr, "bullish"):
                    fvg_bullish = True
                    fvg_strength = _calculate_enhanced_fvg_strength(c_current, candles, i, config, atr)
                else:
                    fvg_zone = None
            
            # Bearish FVG: previous low > next high
            elif c_prev["low"] > c_next["high"]:
                fvg_zone = [c_next["high"], c_prev["low"]]
                zone_size = c_prev["low"] - c_next["high"]
                
                if _is_fvg_valid(c_current, fvg_zone, zone_size, candles, i, config, atr, "bearish"):
                    fvg_bearish = True
                    fvg_strength = _calculate_enhanced_fvg_strength(c_current, candles, i, config, atr)
                else:
                    fvg_zone = None
        
        result.append({
            **candles[i],
            "fvg_bullish": fvg_bullish,
            "fvg_bearish": fvg_bearish,
            "fvg_zone": fvg_zone,
            "fvg_strength": fvg_strength,
            "fvg_filtered": fvg_zone is not None
        })
    
    return result

def _is_fvg_valid(candle: Dict, fvg_zone: List[float], zone_size: float, 
                  candles: List[Dict], index: int, config: FVGFilterConfig, 
                  atr: float, direction: str) -> bool:
    """Check if FVG meets quality criteria"""
    
    # Filter 1: Minimum zone size in pips
    if zone_size < config.min_zone_size_pips:
        return False
    
    # Filter 2: Minimum zone size as percentage of price
    price = candle["close"]
    if (zone_size / price) < config.min_zone_size_percentage:
        return False
    
    # Filter 3: Minimum zone size relative to ATR
    if atr > 0 and zone_size < (atr * config.min_zone_size_atr_multiplier):
        return False
    
    # Filter 4: Volume filter (if volume data available)
    if "volume" in candle and candle["volume"] > 0:
        if not _has_sufficient_volume(candle, candles, index, config):
            return False
    
    # Filter 5: Avoid consolidation FVGs
    if config.avoid_consolidation_fvgs:
        context_start = max(0, index - 20)
        context_candles = candles[context_start:index + 1]
        if is_in_consolidation(context_candles):
            return False
    
    # Filter 6: Momentum filter
    context_start = max(0, index - 10)
    context_candles = candles[context_start:index + 1]
    momentum = calculate_momentum(context_candles)
    if momentum < config.min_momentum_threshold:
        return False
    
    # Filter 7: Weekend filter (if timestamp available)
    if config.exclude_weekend_fvgs and "timestamp" in candle:
        try:
            dt = datetime.fromisoformat(candle["timestamp"].replace("Z", ""))
            if dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return False
        except:
            pass
    
    return True

def _has_sufficient_volume(candle: Dict, candles: List[Dict], index: int, 
                          config: FVGFilterConfig) -> bool:
    """Check if candle has sufficient volume"""
    if "volume" not in candle:
        return True  # Skip volume check if no volume data
    
    # Calculate average volume for context period
    start_idx = max(0, index - config.volume_context_periods)
    context_candles = candles[start_idx:index]
    
    if not context_candles:
        return True
    
    avg_volume = sum(c.get("volume", 0) for c in context_candles) / len(context_candles)
    
    if avg_volume == 0:
        return True
    
    return candle["volume"] >= (avg_volume * config.min_volume_multiplier)

def _calculate_enhanced_fvg_strength(candle: Dict, candles: List[Dict], index: int, 
                                   config: FVGFilterConfig, atr: float) -> float:
    """Calculate enhanced FVG strength score"""
    strength = 0.5  # Base strength
    
    # Factor 1: Zone size relative to ATR
    if candle.get("fvg_zone") and atr > 0:
        zone_size = abs(candle["fvg_zone"][1] - candle["fvg_zone"][0])
        atr_factor = min(zone_size / atr, 3.0) / 3.0
        strength += atr_factor * 0.25
    
    # Factor 2: Volume strength
    if "volume" in candle:
        context_start = max(0, index - config.volume_context_periods)
        context_candles = candles[context_start:index]
        
        if context_candles:
            avg_volume = sum(c.get("volume", 0) for c in context_candles) / len(context_candles)
            if avg_volume > 0:
                volume_factor = min(candle["volume"] / avg_volume, 2.0) / 2.0
                strength += volume_factor * 0.2
    
    # Factor 3: Momentum strength
    context_start = max(0, index - 10)
    context_candles = candles[context_start:index + 1]
    momentum = calculate_momentum(context_candles)
    momentum_factor = min(momentum, 1.0)
    strength += momentum_factor * 0.15
    
    # Factor 4: Market structure context
    if not is_in_consolidation(candles[max(0, index-20):index+1]):
        strength += 0.1  # Bonus for trending market
    
    return min(strength, 1.0)

def get_fvg_quality_metrics(candles: List[Dict]) -> Dict:
    """Get quality metrics for FVG detection"""
    filtered_candles = detect_fvg_with_filters(candles)
    
    total_fvgs = sum(1 for c in filtered_candles if c.get("fvg_zone"))
    high_quality_fvgs = sum(1 for c in filtered_candles if c.get("fvg_strength", 0) >= 0.7)
    
    avg_strength = 0.0
    if total_fvgs > 0:
        total_strength = sum(c.get("fvg_strength", 0) for c in filtered_candles if c.get("fvg_zone"))
        avg_strength = total_strength / total_fvgs
    
    return {
        "total_fvgs": total_fvgs,
        "high_quality_fvgs": high_quality_fvgs,
        "quality_rate": high_quality_fvgs / total_fvgs if total_fvgs > 0 else 0,
        "average_strength": avg_strength,
        "atr": calculate_atr(candles),
        "momentum": calculate_momentum(candles),
        "in_consolidation": is_in_consolidation(candles)
    }

# Example usage and configuration presets
class FVGFilterPresets:
    """Predefined filter configurations for different market conditions"""
    
    @staticmethod
    def conservative() -> FVGFilterConfig:
        """Conservative filtering - only high-quality FVGs"""
        config = FVGFilterConfig()
        config.min_zone_size_pips = 10.0
        config.min_zone_size_percentage = 0.03
        config.min_zone_size_atr_multiplier = 0.5
        config.min_volume_multiplier = 1.5
        config.min_strength_threshold = 0.7
        config.min_momentum_threshold = 0.7
        return config
    
    @staticmethod
    def balanced() -> FVGFilterConfig:
        """Balanced filtering - default settings"""
        return FVGFilterConfig()
    
    @staticmethod
    def aggressive() -> FVGFilterConfig:
        """Aggressive filtering - more FVGs, lower quality threshold"""
        config = FVGFilterConfig()
        config.min_zone_size_pips = 3.0
        config.min_zone_size_percentage = 0.01
        config.min_zone_size_atr_multiplier = 0.2
        config.min_volume_multiplier = 1.0
        config.min_strength_threshold = 0.5
        config.min_momentum_threshold = 0.3
        return config
    
    @staticmethod
    def scalping() -> FVGFilterConfig:
        """Scalping filtering - very tight filters for quick trades"""
        config = FVGFilterConfig()
        config.min_zone_size_pips = 2.0
        config.min_zone_size_percentage = 0.005
        config.min_zone_size_atr_multiplier = 0.1
        config.min_volume_multiplier = 1.8
        config.min_strength_threshold = 0.8
        config.min_momentum_threshold = 0.8
        config.avoid_consolidation_fvgs = True
        return config
