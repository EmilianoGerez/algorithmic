"""
Base Liquidity Pool Manager

This module provides the abstract base class for all liquidity pool managers.
Liquidity pools are areas where price is likely to react (FVGs, pivots, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class LiquidityPool:
    """Base class for all liquidity pools"""
    id: str
    symbol: str
    timeframe: str
    timestamp: datetime
    price_level: float
    pool_type: str
    status: str  # "active", "tested", "invalidated"
    strength: float = 1.0  # Pool strength (0.0-1.0)
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class BaseLiquidityPoolManager(ABC):
    """Abstract base class for all liquidity pool managers"""
    
    def __init__(self, db_session: Session, cache_manager: Optional[Any] = None):
        self.db = db_session
        self.cache = cache_manager
        self.pool_type = self._get_pool_type()
    
    @abstractmethod
    def _get_pool_type(self) -> str:
        """Return the pool type identifier"""
        pass
    
    @abstractmethod
    def detect_pools(self, candles: List[Dict], symbol: str, timeframe: str) -> List[LiquidityPool]:
        """Detect new liquidity pools from candle data"""
        pass
    
    @abstractmethod
    def update_pool_status(self, pools: List[LiquidityPool], current_candles: List[Dict]) -> List[LiquidityPool]:
        """Update the status of existing pools based on new market data"""
        pass
    
    @abstractmethod
    def save_pools(self, pools: List[LiquidityPool]) -> bool:
        """Save pools to database"""
        pass
    
    @abstractmethod
    def load_active_pools(self, symbol: str, timeframe: str, 
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[LiquidityPool]:
        """Load active pools from database"""
        pass
    
    def get_cache_key(self, symbol: str, timeframe: str, start: str, end: str) -> str:
        """Generate cache key for pools"""
        return f"{self.pool_type}:pools:{symbol}:{timeframe}:{start}:{end}"
    
    def calculate_pool_strength(self, pool: LiquidityPool, market_context: Dict) -> float:
        """Calculate the strength/importance of a liquidity pool"""
        # Base implementation - can be overridden
        return 1.0
    
    def filter_pools_by_strength(self, pools: List[LiquidityPool], 
                                min_strength: float = 0.5) -> List[LiquidityPool]:
        """Filter pools by minimum strength threshold"""
        return [pool for pool in pools if pool.strength >= min_strength]
    
    def get_pools_near_price(self, pools: List[LiquidityPool], 
                           current_price: float, 
                           distance_pct: float = 0.02) -> List[LiquidityPool]:
        """Get pools within a certain percentage distance from current price"""
        filtered = []
        for pool in pools:
            distance = abs(pool.price_level - current_price) / current_price
            if distance <= distance_pct:
                filtered.append(pool)
        return filtered
    
    def cleanup_old_pools(self, symbol: str, timeframe: str, 
                         days_old: int = 30) -> int:
        """Remove old/stale pools from database"""
        # Implementation depends on specific pool type
        return 0
