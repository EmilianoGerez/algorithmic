"""
FVG Liquidity Pool Detector

Detects when price interacts with Fair Value Gaps (FVG) liquidity pools
"""

from typing import List, Dict
from datetime import datetime
from ..composable_strategy import LiquidityPoolDetector, LiquidityPoolEvent, LiquidityPoolType, TrendDirection


class FVGPoolDetector(LiquidityPoolDetector):
    """Detects FVG liquidity pool interactions"""
    
    def __init__(self, touch_threshold: float = 0.001):
        """
        Initialize FVG pool detector
        
        Args:
            touch_threshold: Percentage threshold for considering a "touch" (0.001 = 0.1%)
        """
        self.touch_threshold = touch_threshold
    
    def detect_events(self, candles: List[Dict], pools: List[Dict]) -> List[LiquidityPoolEvent]:
        """
        Detect FVG interactions in the candle data
        
        Args:
            candles: List of OHLCV candles
            pools: List of FVG pools from HTF
        
        Returns:
            List of liquidity pool events
        """
        events = []
        
        # Filter for FVG pools - check different possible keys
        fvg_pools = []
        for pool in pools:
            if (pool.get('pool_type') == 'fvg' or 
                'fvg' in pool or 
                pool.get('direction') in ['bullish', 'bearish']):
                fvg_pools.append(pool)
        
        for pool in fvg_pools:
            # Extract pool information with fallback keys
            direction_str = pool.get('direction', 'bullish')
            pool_direction = TrendDirection.BULLISH if direction_str == 'bullish' else TrendDirection.BEARISH
            zone_low = pool.get('zone_low', 0)
            zone_high = pool.get('zone_high', 0)
            pool_id = pool.get('id', f"fvg_{pool.get('timestamp', '')}")
            
            # Check each candle for interaction
            for candle in candles:
                event = self._check_fvg_interaction(candle, pool, pool_direction, zone_low, zone_high, pool_id)
                if event:
                    events.append(event)
        
        return events
    
    def _check_fvg_interaction(self, candle: Dict, pool: Dict, direction: TrendDirection, 
                              zone_low: float, zone_high: float, pool_id: str) -> LiquidityPoolEvent:
        """Check if a candle interacts with an FVG"""
        
        candle_high = candle['high']
        candle_low = candle['low']
        candle_close = candle['close']
        timestamp = datetime.fromisoformat(candle['timestamp'].replace('Z', ''))
        
        # Calculate touch thresholds
        zone_size = zone_high - zone_low
        touch_buffer = zone_size * self.touch_threshold
        
        interaction_type = None
        
        # Check for different types of interactions
        if direction == TrendDirection.BULLISH:  # Bullish FVG
            # Price should come from below and touch/enter the zone
            if candle_low <= zone_high + touch_buffer and candle_high >= zone_low - touch_buffer:
                if candle_close > zone_high:
                    interaction_type = "swept"  # Price swept through the FVG
                elif candle_low <= zone_low:
                    interaction_type = "penetrated"  # Price penetrated below FVG
                else:
                    interaction_type = "touched"  # Price touched the FVG
        
        else:  # Bearish FVG
            # Price should come from above and touch/enter the zone
            if candle_high >= zone_low - touch_buffer and candle_low <= zone_high + touch_buffer:
                if candle_close < zone_low:
                    interaction_type = "swept"  # Price swept through the FVG
                elif candle_high >= zone_high:
                    interaction_type = "penetrated"  # Price penetrated above FVG
                else:
                    interaction_type = "touched"  # Price touched the FVG
        
        # Create event if interaction detected
        if interaction_type:
            return LiquidityPoolEvent(
                pool_type=LiquidityPoolType.FVG,
                timestamp=timestamp,
                price=candle_close,
                direction=direction,
                zone_low=zone_low,
                zone_high=zone_high,
                status=interaction_type,
                pool_id=pool_id,
                timeframe="15T",  # LTF timeframe
                metadata={
                    "candle_high": candle_high,
                    "candle_low": candle_low,
                    "candle_close": candle_close,
                    "zone_size": zone_size,
                    "pool_data": pool
                }
            )
        
        return None


class PivotPoolDetector(LiquidityPoolDetector):
    """Detects pivot point liquidity pool interactions"""
    
    def __init__(self, sweep_threshold: float = 0.0005):
        """
        Initialize pivot pool detector
        
        Args:
            sweep_threshold: Percentage threshold for considering a "sweep" (0.0005 = 0.05%)
        """
        self.sweep_threshold = sweep_threshold
    
    def detect_events(self, candles: List[Dict], pools: List[Dict]) -> List[LiquidityPoolEvent]:
        """
        Detect pivot point interactions in the candle data
        
        Args:
            candles: List of OHLCV candles
            pools: List of pivot pools from HTF
        
        Returns:
            List of liquidity pool events
        """
        events = []
        
        # Filter for pivot pools - check different possible keys
        pivot_pools = []
        for pool in pools:
            if (pool.get('pool_type') == 'pivot' or 
                'pivot' in pool or 
                pool.get('pivot_type') in ['high', 'low', 'resistance', 'support']):
                pivot_pools.append(pool)
        
        for pool in pivot_pools:
            # Extract pool information
            pivot_type = pool.get('pivot_type', pool.get('type', 'unknown'))
            price_level = pool.get('price_level', pool.get('price', 0))
            pool_id = pool.get('id', f"pivot_{pool.get('timestamp', '')}")
            
            # Determine direction based on pivot type
            if pivot_type in ['high', 'resistance']:
                direction = TrendDirection.BEARISH
            elif pivot_type in ['low', 'support']:
                direction = TrendDirection.BULLISH
            else:
                direction = TrendDirection.NEUTRAL
            
            # Check each candle for interaction
            for candle in candles:
                event = self._check_pivot_interaction(candle, pool, direction, price_level, pool_id, pivot_type)
                if event:
                    events.append(event)
        
        return events
    
    def _check_pivot_interaction(self, candle: Dict, pool: Dict, direction: TrendDirection, 
                                price_level: float, pool_id: str, pivot_type: str) -> LiquidityPoolEvent:
        """Check if a candle interacts with a pivot point"""
        
        candle_high = candle['high']
        candle_low = candle['low']
        candle_close = candle['close']
        timestamp = datetime.fromisoformat(candle['timestamp'].replace('Z', ''))
        
        # Calculate sweep thresholds
        sweep_buffer = price_level * self.sweep_threshold
        
        interaction_type = None
        
        # Check for pivot interactions
        if pivot_type in ['high', 'resistance']:
            # Check for sweep above resistance
            if candle_high >= price_level + sweep_buffer:
                interaction_type = "swept"
            elif candle_high >= price_level - sweep_buffer:
                interaction_type = "touched"
        
        elif pivot_type in ['low', 'support']:
            # Check for sweep below support
            if candle_low <= price_level - sweep_buffer:
                interaction_type = "swept"
            elif candle_low <= price_level + sweep_buffer:
                interaction_type = "touched"
        
        # Create event if interaction detected
        if interaction_type:
            return LiquidityPoolEvent(
                pool_type=LiquidityPoolType.PIVOT,
                timestamp=timestamp,
                price=candle_close,
                direction=direction,
                zone_low=price_level - sweep_buffer,
                zone_high=price_level + sweep_buffer,
                status=interaction_type,
                pool_id=pool_id,
                timeframe="15T",  # LTF timeframe
                metadata={
                    "candle_high": candle_high,
                    "candle_low": candle_low,
                    "candle_close": candle_close,
                    "price_level": price_level,
                    "pivot_type": pivot_type,
                    "pool_data": pool
                }
            )
        
        return None
