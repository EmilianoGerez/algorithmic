"""
FVG Pool Manager - Updated to use Unified FVG Management System
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
import uuid
from sqlalchemy.orm import Session
from src.db.models.fvg import FVG as FVGModel
from src.core.liquidity.unified_fvg_manager import UnifiedFVGManager, FVGZone, FVGStatus
from src.core.liquidity.liquidity_pool import LiquidityPool


class FVGPool(LiquidityPool):
    """
    FVG Pool - updated to work with unified FVG system
    """
    def __init__(self, id: str, symbol: str, timeframe: str, timestamp: datetime,
                 price_level: float, pool_type: str = "fvg", status: str = FVGStatus.ACTIVE,
                 zone_low: float = None, zone_high: float = None, direction: str = None,
                 is_inverse: bool = False, touch_count: int = 0, mitigation_percentage: float = 0.0,
                 confidence: float = 0.5, strength: float = 0.5):
        super().__init__(id, symbol, timeframe, timestamp, price_level, pool_type, status)
        self.zone_low = zone_low
        self.zone_high = zone_high
        self.direction = direction
        self.is_inverse = is_inverse
        self.touch_count = touch_count
        self.mitigation_percentage = mitigation_percentage
        self.confidence = confidence
        self.strength = strength
        self.last_touch_time = None

    def to_fvg_zone(self) -> FVGZone:
        """Convert FVGPool to FVGZone for unified management"""
        return FVGZone(
            id=self.id,
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp=self.timestamp,
            direction=self.direction,
            zone_low=self.zone_low,
            zone_high=self.zone_high,
            status=self.status,
            touch_count=self.touch_count,
            max_penetration_pct=self.mitigation_percentage,
            confidence=self.confidence,
            strength=self.strength,
            last_touch_time=self.last_touch_time
        )

    @classmethod
    def from_fvg_zone(cls, zone: FVGZone) -> 'FVGPool':
        """Create FVGPool from FVGZone"""
        pool = cls(
            id=zone.id,
            symbol=zone.symbol,
            timeframe=zone.timeframe,
            timestamp=zone.timestamp,
            price_level=(zone.zone_low + zone.zone_high) / 2,
            status=zone.status,
            zone_low=zone.zone_low,
            zone_high=zone.zone_high,
            direction=zone.direction,
            is_inverse=False,  # iFVG removed as requested
            touch_count=zone.touch_count,
            mitigation_percentage=zone.max_penetration_pct,
            confidence=zone.confidence,
            strength=zone.strength
        )
        pool.last_touch_time = zone.last_touch_time
        return pool


class FVGPoolManager:
    """
    FVG Pool Manager - updated to use Unified FVG Management System
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.unified_manager = UnifiedFVGManager(db_session)
    
    def create_fvg_pools(self, candles: List[Dict], symbol: str, timeframe: str) -> List[FVGPool]:
        """
        Create FVG pools using unified detection system
        """
        # Use unified manager to detect FVG zones
        zones = self.unified_manager.detect_fvg_zones(candles)
        
        # Convert zones to pools
        pools = []
        for zone in zones:
            pool = FVGPool.from_fvg_zone(zone)
            pools.append(pool)
        
        return pools
    
    def update_pool_status(self, pools: List[FVGPool], candles: List[Dict]) -> List[FVGPool]:
        """
        Update pool status using unified FVG management
        """
        # Convert pools to zones
        zones = [pool.to_fvg_zone() for pool in pools]
        
        # Update zones using unified manager
        updated_zones = self.unified_manager.update_fvg_status(zones, candles)
        
        # Convert back to pools
        updated_pools = []
        for zone in updated_zones:
            pool = FVGPool.from_fvg_zone(zone)
            updated_pools.append(pool)
        
        return updated_pools
    
    def save_pools(self, pools: List[FVGPool]) -> bool:
        """
        Save FVG pools using unified system
        """
        # Convert pools to zones
        zones = [pool.to_fvg_zone() for pool in pools]
        
        # Save using unified manager
        return self.unified_manager.save_zones(zones)
    
    def load_active_pools(self, symbol: str, timeframe: str,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[FVGPool]:
        """
        Load active FVG pools using unified system
        """
        # Load zones using unified manager
        zones = self.unified_manager.load_active_zones(symbol, timeframe, start_time, end_time)
        
        # Convert zones to pools
        pools = []
        for zone in zones:
            pool = FVGPool.from_fvg_zone(zone)
            pools.append(pool)
        
        return pools
    
    def get_htf_pools_for_ltf_analysis(self, symbol: str, htf_timeframe: str, 
                                      ltf_timeframe: str) -> List[FVGPool]:
        """
        Get HTF FVG pools for LTF analysis with enhanced filtering
        """
        pools = self.load_active_pools(symbol, htf_timeframe)
        
        # Filter for strong, high-confidence pools
        strong_pools = []
        for pool in pools:
            if (pool.confidence > 0.6 and 
                pool.strength > 0.5 and 
                pool.status in [FVGStatus.ACTIVE, FVGStatus.TESTED]):
                strong_pools.append(pool)
        
        return strong_pools
    
    def get_pool_summary(self, pools: List[FVGPool]) -> Dict:
        """
        Get summary statistics for FVG pools
        """
        zones = [pool.to_fvg_zone() for pool in pools]
        return self.unified_manager.get_zone_summary(zones)
    
    def cleanup_old_pools(self, symbol: str, timeframe: str, days_old: int = 30) -> int:
        """
        Remove old FVG pools from database
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        deleted_count = self.db.query(FVGModel).filter(
            FVGModel.symbol == symbol,
            FVGModel.timeframe == timeframe,
            FVGModel.timestamp < cutoff_date
        ).delete()
        
        self.db.commit()
        return deleted_count
    
    def get_pools_by_confidence(self, pools: List[FVGPool], min_confidence: float = 0.5) -> List[FVGPool]:
        """
        Filter pools by minimum confidence level
        """
        return [pool for pool in pools if pool.confidence >= min_confidence]
    
    def get_pools_by_status(self, pools: List[FVGPool], status: str) -> List[FVGPool]:
        """
        Filter pools by status
        """
        return [pool for pool in pools if pool.status == status]
    
    def get_pools_by_direction(self, pools: List[FVGPool], direction: str) -> List[FVGPool]:
        """
        Filter pools by direction
        """
        return [pool for pool in pools if pool.direction == direction]
    
    # Legacy methods for backward compatibility
    def set_filter_preset(self, preset: str):
        """Legacy method for backward compatibility"""
        pass
    
    def _get_pool_type(self) -> str:
        """Legacy method for backward compatibility"""
        return "fvg"
