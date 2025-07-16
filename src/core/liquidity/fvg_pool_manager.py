"""
FVG (Fair Value Gap) Liquidity Pool Manager

This module manages FVG liquidity pools for both HTF and LTF analysis.
HTF FVGs are tracked for long-term liquidity zones.
LTF FVGs (including inverse FVGs) are used for local reactions.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import uuid

from src.core.liquidity.base_pool_manager import BaseLiquidityPoolManager, LiquidityPool
from src.db.models.fvg import FVG as FVGModel
from src.core.signals.fvg import detect_fvg
from sqlalchemy.orm import Session


@dataclass
class FVGPool(LiquidityPool):
    """FVG-specific liquidity pool"""
    zone_low: float = 0.0
    zone_high: float = 0.0
    direction: str = "bullish"  # "bullish" or "bearish"
    is_inverse: bool = False
    touch_count: int = 0
    last_touch_time: Optional[datetime] = None
    mitigation_percentage: float = 0.0
    
    def __post_init__(self):
        super().__post_init__()
        self.price_level = (self.zone_low + self.zone_high) / 2
        self.pool_type = "fvg"


class FVGPoolManager(BaseLiquidityPoolManager):
    """Manager for FVG liquidity pools"""
    
    def __init__(self, db_session: Session, cache_manager: Optional[object] = None):
        super().__init__(db_session, cache_manager)
        self.max_fvg_age_days = 30  # How long to keep FVGs active
    
    def _get_pool_type(self) -> str:
        return "fvg"
    
    def detect_pools(self, candles: List[Dict], symbol: str, timeframe: str) -> List[FVGPool]:
        """Detect FVG pools from candle data"""
        fvg_candles = detect_fvg(candles)
        pools = []
        
        for i, candle in enumerate(fvg_candles):
            if candle.get("fvg_zone"):
                zone_low, zone_high = sorted(candle["fvg_zone"])
                direction = "bullish" if candle.get("fvg_bullish") else "bearish"
                
                pool = FVGPool(
                    id=f"fvg_{symbol}_{timeframe}_{i}_{uuid.uuid4().hex[:8]}",
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromisoformat(candle["timestamp"].replace("Z", "")),
                    price_level=(zone_low + zone_high) / 2,
                    pool_type="fvg",
                    status="active",
                    zone_low=zone_low,
                    zone_high=zone_high,
                    direction=direction,
                    strength=self._calculate_fvg_strength(candle, candles[max(0, i-5):i+6])
                )
                pools.append(pool)
        
        return pools
    
    def detect_inverse_fvg(self, candles: List[Dict], symbol: str, timeframe: str,
                          original_direction: str) -> List[FVGPool]:
        """Detect inverse FVGs after liquidity grab"""
        inverse_pools = []
        fvg_candles = detect_fvg(candles)
        
        for i, candle in enumerate(fvg_candles):
            if candle.get("fvg_zone"):
                zone_low, zone_high = sorted(candle["fvg_zone"])
                direction = "bullish" if candle.get("fvg_bullish") else "bearish"
                
                # Check if this is an inverse FVG (opposite direction)
                if direction != original_direction:
                    pool = FVGPool(
                        id=f"ifvg_{symbol}_{timeframe}_{i}_{uuid.uuid4().hex[:8]}",
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=datetime.fromisoformat(candle["timestamp"].replace("Z", "")),
                        price_level=(zone_low + zone_high) / 2,
                        pool_type="fvg",
                        status="active",
                        zone_low=zone_low,
                        zone_high=zone_high,
                        direction=direction,
                        is_inverse=True,
                        strength=self._calculate_fvg_strength(candle, candles[max(0, i-5):i+6])
                    )
                    inverse_pools.append(pool)
        
        return inverse_pools
    
    def update_pool_status(self, pools: List[FVGPool], current_candles: List[Dict]) -> List[FVGPool]:
        """Update FVG pool status based on current market data"""
        updated_pools = []
        
        for pool in pools:
            if pool.status == "invalidated":
                continue
                
            # Only check candles that come AFTER the FVG formation
            for candle in current_candles:
                candle_time = datetime.fromisoformat(candle["timestamp"].replace("Z", ""))
                
                # Skip candles that are before or at the FVG formation time
                if candle_time <= pool.timestamp:
                    continue
                    
                open_price = candle["open"]
                close_price = candle["close"]
                high_price = candle["high"]
                low_price = candle["low"]
                
                body_high = max(open_price, close_price)
                body_low = min(open_price, close_price)
                
                # Check for FVG touch/mitigation
                if self._is_fvg_touched(pool, high_price, low_price, body_high, body_low):
                    pool.touch_count += 1
                    pool.last_touch_time = candle_time
                    
                    # Calculate mitigation percentage using full candle range
                    mitigation_pct = self._calculate_mitigation_percentage(pool, high_price, low_price)
                    pool.mitigation_percentage = max(pool.mitigation_percentage, mitigation_pct)
                    
                    # Update status based on mitigation - more conservative thresholds for 4H timeframes
                    if mitigation_pct > 0.3:  # 30% mitigation threshold for "tested"
                        pool.status = "tested"
                    # Only invalidate if price fully closes through the zone (handled in _is_fvg_invalidated)
                    # Remove automatic invalidation based on mitigation percentage
                
                # Check for complete invalidation
                elif self._is_fvg_invalidated(pool, close_price):
                    pool.status = "invalidated"
            
            updated_pools.append(pool)
        
        return updated_pools
    
    def save_pools(self, pools: List[FVGPool]) -> bool:
        """Save FVG pools to database with proper upsert handling"""
        try:
            for pool in pools:
                # Check if FVG already exists
                existing_fvg = self.db.query(FVGModel).filter(
                    FVGModel.timestamp == pool.timestamp,
                    FVGModel.timeframe == pool.timeframe,
                    FVGModel.symbol == pool.symbol
                ).first()
                
                if existing_fvg:
                    # Update existing FVG
                    existing_fvg.direction = pool.direction
                    existing_fvg.zone_low = pool.zone_low
                    existing_fvg.zone_high = pool.zone_high
                    existing_fvg.status = pool.status
                    existing_fvg.iFVG = pool.is_inverse
                    existing_fvg.touched = pool.touch_count > 0
                    existing_fvg.penetration_pct = pool.mitigation_percentage
                else:
                    # Create new FVG
                    fvg_model = FVGModel(
                        id=uuid.uuid4(),
                        symbol=pool.symbol,
                        timeframe=pool.timeframe,
                        timestamp=pool.timestamp,
                        direction=pool.direction,
                        zone_low=pool.zone_low,
                        zone_high=pool.zone_high,
                        status=pool.status,
                        iFVG=pool.is_inverse,
                        touched=pool.touch_count > 0,
                        penetration_pct=pool.mitigation_percentage
                    )
                    self.db.add(fvg_model)
            
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error saving FVG pools: {e}")
            self.db.rollback()
            return False
    
    def load_active_pools(self, symbol: str, timeframe: str,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[FVGPool]:
        """Load active FVG pools from database"""
        query = self.db.query(FVGModel).filter(
            FVGModel.symbol == symbol,
            FVGModel.timeframe == timeframe,
            FVGModel.status.in_(["active", "tested"])
        )
        
        if start_time:
            query = query.filter(FVGModel.timestamp >= start_time)
        if end_time:
            query = query.filter(FVGModel.timestamp <= end_time)
        
        fvg_models = query.all()
        
        pools = []
        for model in fvg_models:
            pool = FVGPool(
                id=f"fvg_{symbol}_{timeframe}_{str(model.id)[:8]}",
                symbol=model.symbol,
                timeframe=model.timeframe,
                timestamp=model.timestamp,
                price_level=(model.zone_low + model.zone_high) / 2,
                pool_type="fvg",
                status=model.status,
                zone_low=model.zone_low,
                zone_high=model.zone_high,
                direction=model.direction,
                is_inverse=model.iFVG,
                touch_count=1 if model.touched else 0,
                mitigation_percentage=model.penetration_pct or 0.0
            )
            pools.append(pool)
        
        return pools
    
    def get_htf_pools_for_ltf_analysis(self, symbol: str, htf_timeframe: str, 
                                      ltf_timeframe: str) -> List[FVGPool]:
        """Get HTF FVG pools for LTF analysis"""
        pools = self.load_active_pools(symbol, htf_timeframe)
        
        # Filter for strong, untested pools
        strong_pools = [p for p in pools if p.strength > 0.6 and p.status == "active"]
        
        return strong_pools
    
    def _calculate_fvg_strength(self, fvg_candle: Dict, context_candles: List[Dict]) -> float:
        """Calculate the strength of an FVG based on context"""
        strength = 0.5  # Base strength
        
        # Factor 1: Size of the FVG
        if fvg_candle.get("fvg_zone"):
            zone_size = abs(fvg_candle["fvg_zone"][1] - fvg_candle["fvg_zone"][0])
            avg_range = sum(c["high"] - c["low"] for c in context_candles) / len(context_candles)
            size_factor = min(zone_size / avg_range, 2.0) / 2.0
            strength += size_factor * 0.3
        
        # Factor 2: Volume context (if available)
        if "volume" in fvg_candle:
            avg_volume = sum(c.get("volume", 0) for c in context_candles) / len(context_candles)
            if avg_volume > 0:
                volume_factor = min(fvg_candle["volume"] / avg_volume, 2.0) / 2.0
                strength += volume_factor * 0.2
        
        return min(strength, 1.0)
    
    def _is_fvg_touched(self, pool: FVGPool, high: float, low: float, 
                       body_high: float, body_low: float) -> bool:
        """Check if FVG is touched by price action"""
        # Check if price wicks or body overlaps with FVG zone
        return not (high < pool.zone_low or low > pool.zone_high)
    
    def _calculate_mitigation_percentage(self, pool: FVGPool, high_price: float, low_price: float) -> float:
        """Calculate how much of the FVG has been mitigated using full candle range"""
        zone_size = pool.zone_high - pool.zone_low
        if zone_size <= 0:
            return 0.0
        
        # Calculate overlap between full candle range and FVG zone
        overlap_low = max(low_price, pool.zone_low)
        overlap_high = min(high_price, pool.zone_high)
        
        if overlap_high <= overlap_low:
            return 0.0
        
        overlap_size = overlap_high - overlap_low
        return overlap_size / zone_size
    
    def _is_fvg_invalidated(self, pool: FVGPool, close_price: float) -> bool:
        """Check if FVG is completely invalidated - requires closing through the zone"""
        if pool.direction == "bullish":
            # For bullish FVG, invalidated only if price closes below zone_low
            return close_price < pool.zone_low
        else:
            # For bearish FVG, invalidated only if price closes above zone_high
            return close_price > pool.zone_high
    
    def cleanup_old_pools(self, symbol: str, timeframe: str, days_old: int = 30) -> int:
        """Remove old FVG pools from database"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        deleted_count = self.db.query(FVGModel).filter(
            FVGModel.symbol == symbol,
            FVGModel.timeframe == timeframe,
            FVGModel.timestamp < cutoff_date
        ).delete()
        
        self.db.commit()
        return deleted_count
