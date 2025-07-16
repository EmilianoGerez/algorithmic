"""
Pivot/Swing Point Liquidity Pool Manager

This module manages pivot point liquidity pools for both HTF and LTF analysis.
Pivot points represent key swing highs and lows that act as support/resistance.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import uuid

from src.core.liquidity.base_pool_manager import BaseLiquidityPoolManager, LiquidityPool
from src.db.models.pivot import Pivot as PivotModel
from src.core.signals.pivot_points import detect_pivots
from sqlalchemy.orm import Session


@dataclass
class PivotPool(LiquidityPool):
    """Pivot-specific liquidity pool"""
    pivot_type: str = "high"  # "high" or "low"
    confirmed: bool = False
    test_count: int = 0
    last_test_time: Optional[datetime] = None
    broken: bool = False
    broken_time: Optional[datetime] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.pool_type = "pivot"


class PivotPoolManager(BaseLiquidityPoolManager):
    """Manager for pivot point liquidity pools"""
    
    def __init__(self, db_session: Session, cache_manager: Optional[object] = None):
        super().__init__(db_session, cache_manager)
        self.confirmation_lookback = 5  # Candles to confirm pivot
        self.max_pivot_age_days = 60  # How long to keep pivots active
    
    def _get_pool_type(self) -> str:
        return "pivot"
    
    def detect_pools(self, candles: List[Dict], symbol: str, timeframe: str) -> List[PivotPool]:
        """Detect pivot pools from candle data"""
        pivot_candles = detect_pivots(candles)
        pools = []
        
        for i, candle in enumerate(pivot_candles):
            if candle.get("potential_swing_high"):
                pool = PivotPool(
                    id=f"pivot_{symbol}_{timeframe}_{i}_high_{uuid.uuid4().hex[:8]}",
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromisoformat(candle["timestamp"].replace("Z", "")),
                    price_level=candle["high"],
                    pool_type="pivot",
                    status="active",
                    pivot_type="high",
                    confirmed=self._is_pivot_confirmed(i, candles, "high"),
                    strength=self._calculate_pivot_strength(i, candles, "high")
                )
                pools.append(pool)
            
            if candle.get("potential_swing_low"):
                pool = PivotPool(
                    id=f"pivot_{symbol}_{timeframe}_{i}_low_{uuid.uuid4().hex[:8]}",
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromisoformat(candle["timestamp"].replace("Z", "")),
                    price_level=candle["low"],
                    pool_type="pivot",
                    status="active",
                    pivot_type="low",
                    confirmed=self._is_pivot_confirmed(i, candles, "low"),
                    strength=self._calculate_pivot_strength(i, candles, "low")
                )
                pools.append(pool)
        
        return pools
    
    def detect_market_structure_pivots(self, candles: List[Dict], symbol: str, 
                                     timeframe: str) -> List[PivotPool]:
        """Detect pivots that form market structure (HH, HL, LH, LL)"""
        pools = self.detect_pools(candles, symbol, timeframe)
        
        # Enhance with market structure analysis
        for pool in pools:
            pool.strength = self._calculate_structure_strength(pool, pools)
        
        return pools
    
    def update_pool_status(self, pools: List[PivotPool], current_candles: List[Dict]) -> List[PivotPool]:
        """Update pivot pool status based on current market data"""
        updated_pools = []
        
        for pool in pools:
            if pool.status == "invalidated":
                continue
            
            # Check each candle for interactions with the pivot
            for candle in current_candles:
                candle_time = datetime.fromisoformat(candle["timestamp"].replace("Z", ""))
                
                # Check for pivot test
                if self._is_pivot_tested(pool, candle):
                    pool.test_count += 1
                    pool.last_test_time = candle_time
                    pool.status = "tested"
                
                # Check for pivot break
                elif self._is_pivot_broken(pool, candle):
                    pool.broken = True
                    pool.broken_time = candle_time
                    pool.status = "invalidated"
                    
                    # Create new pivot if structure shifts
                    if pool.pivot_type == "high" and candle["close"] > pool.price_level:
                        # Potential higher high
                        pass
                    elif pool.pivot_type == "low" and candle["close"] < pool.price_level:
                        # Potential lower low
                        pass
            
            updated_pools.append(pool)
        
        return updated_pools
    
    def save_pools(self, pools: List[PivotPool]) -> bool:
        """Save pivot pools to database"""
        try:
            for pool in pools:
                pivot_model = PivotModel(
                    id=uuid.uuid4(),  # Generate a fresh UUID for each pool
                    symbol=pool.symbol,
                    timeframe=pool.timeframe,
                    timestamp=pool.timestamp,
                    price=pool.price_level,
                    type=pool.pivot_type,
                    confirmed=pool.confirmed
                )
                self.db.merge(pivot_model)  # Use merge to handle updates
            
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error saving pivot pools: {e}")
            self.db.rollback()
            return False
    
    def load_active_pools(self, symbol: str, timeframe: str,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[PivotPool]:
        """Load active pivot pools from database"""
        query = self.db.query(PivotModel).filter(
            PivotModel.symbol == symbol,
            PivotModel.timeframe == timeframe
        )
        
        if start_time:
            query = query.filter(PivotModel.timestamp >= start_time)
        if end_time:
            query = query.filter(PivotModel.timestamp <= end_time)
        
        pivot_models = query.all()
        
        pools = []
        for model in pivot_models:
            pool = PivotPool(
                id=f"pivot_{symbol}_{timeframe}_{str(model.id)[:8]}",
                symbol=model.symbol,
                timeframe=model.timeframe,
                timestamp=model.timestamp,
                price_level=model.price,
                pool_type="pivot",
                status="active",  # Re-evaluate status on load
                pivot_type=model.type,
                confirmed=model.confirmed
            )
            pools.append(pool)
        
        return pools
    
    def get_significant_pivots(self, symbol: str, timeframe: str, 
                             min_strength: float = 0.7) -> List[PivotPool]:
        """Get pivots with high significance for market structure"""
        pools = self.load_active_pools(symbol, timeframe)
        return [p for p in pools if p.strength >= min_strength and p.confirmed]
    
    def get_nearest_pivots(self, symbol: str, timeframe: str, current_price: float,
                          max_distance_pct: float = 0.05) -> Dict[str, List[PivotPool]]:
        """Get nearest significant pivots above and below current price"""
        pools = self.load_active_pools(symbol, timeframe)
        
        highs_above = [p for p in pools if p.pivot_type == "high" and p.price_level > current_price]
        lows_below = [p for p in pools if p.pivot_type == "low" and p.price_level < current_price]
        
        # Filter by distance
        distance_threshold = current_price * max_distance_pct
        highs_above = [p for p in highs_above if p.price_level - current_price <= distance_threshold]
        lows_below = [p for p in lows_below if current_price - p.price_level <= distance_threshold]
        
        # Sort by proximity
        highs_above.sort(key=lambda p: p.price_level - current_price)
        lows_below.sort(key=lambda p: current_price - p.price_level)
        
        return {
            "resistance_above": highs_above,
            "support_below": lows_below
        }
    
    def _is_pivot_confirmed(self, pivot_index: int, candles: List[Dict], pivot_type: str) -> bool:
        """Check if pivot is confirmed by subsequent price action"""
        if pivot_index >= len(candles) - self.confirmation_lookback:
            return False
        
        pivot_candle = candles[pivot_index]
        pivot_price = pivot_candle["high"] if pivot_type == "high" else pivot_candle["low"]
        
        # Check confirmation candles
        for i in range(pivot_index + 1, min(pivot_index + self.confirmation_lookback + 1, len(candles))):
            candle = candles[i]
            if pivot_type == "high" and candle["high"] > pivot_price:
                return False
            elif pivot_type == "low" and candle["low"] < pivot_price:
                return False
        
        return True
    
    def _calculate_pivot_strength(self, pivot_index: int, candles: List[Dict], pivot_type: str) -> float:
        """Calculate the strength of a pivot point"""
        if pivot_index < 5 or pivot_index >= len(candles) - 5:
            return 0.5
        
        pivot_candle = candles[pivot_index]
        pivot_price = pivot_candle["high"] if pivot_type == "high" else pivot_candle["low"]
        
        strength = 0.5
        
        # Factor 1: How far the pivot extends beyond nearby candles
        lookback_range = 5
        comparison_candles = candles[pivot_index - lookback_range:pivot_index + lookback_range + 1]
        
        if pivot_type == "high":
            max_other_high = max(c["high"] for c in comparison_candles if c != pivot_candle)
            if max_other_high > 0:
                extension_factor = (pivot_price - max_other_high) / max_other_high
                strength += min(extension_factor * 2, 0.3)
        else:
            min_other_low = min(c["low"] for c in comparison_candles if c != pivot_candle)
            if min_other_low > 0:
                extension_factor = (min_other_low - pivot_price) / min_other_low
                strength += min(extension_factor * 2, 0.3)
        
        # Factor 2: Volume (if available)
        if "volume" in pivot_candle:
            avg_volume = sum(c.get("volume", 0) for c in comparison_candles) / len(comparison_candles)
            if avg_volume > 0:
                volume_factor = min(pivot_candle["volume"] / avg_volume, 2.0) / 2.0
                strength += volume_factor * 0.2
        
        return min(strength, 1.0)
    
    def _calculate_structure_strength(self, pool: PivotPool, all_pools: List[PivotPool]) -> float:
        """Calculate strength based on market structure context"""
        # This is a simplified version - can be enhanced with proper structure analysis
        base_strength = pool.strength
        
        # Count nearby pivots of same type
        nearby_pivots = [p for p in all_pools 
                        if p.pivot_type == pool.pivot_type 
                        and abs(p.price_level - pool.price_level) / pool.price_level < 0.01]
        
        if len(nearby_pivots) > 1:
            base_strength += 0.1  # Confluence adds strength
        
        return min(base_strength, 1.0)
    
    def _is_pivot_tested(self, pool: PivotPool, candle: Dict) -> bool:
        """Check if pivot is tested by price action"""
        tolerance = 0.001  # 0.1% tolerance
        pivot_price = pool.price_level
        
        if pool.pivot_type == "high":
            return candle["high"] >= pivot_price * (1 - tolerance)
        else:
            return candle["low"] <= pivot_price * (1 + tolerance)
    
    def _is_pivot_broken(self, pool: PivotPool, candle: Dict) -> bool:
        """Check if pivot is broken by price action"""
        pivot_price = pool.price_level
        
        if pool.pivot_type == "high":
            return candle["close"] > pivot_price
        else:
            return candle["close"] < pivot_price
    
    def cleanup_old_pools(self, symbol: str, timeframe: str, days_old: int = 60) -> int:
        """Remove old pivot pools from database"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        deleted_count = self.db.query(PivotModel).filter(
            PivotModel.symbol == symbol,
            PivotModel.timeframe == timeframe,
            PivotModel.timestamp < cutoff_date
        ).delete()
        
        self.db.commit()
        return deleted_count
