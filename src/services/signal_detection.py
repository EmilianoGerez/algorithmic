from typing import Dict, List, Literal, Optional
from src.db.models.candle import Candle
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.core.signals import pivot_points, fvg, fvg_tracker
from src.core.signals.multi_timeframe_engine import MultiTimeframeSignalEngine, TradingSignal
from src.infrastructure.cache.enhanced_cache_manager import CacheManager
import redis
import json
from hashlib import sha256
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot
from sqlalchemy.orm import Session
from datetime import datetime


class SignalDetectionService:
    """
    Refactored Signal Detection Service with separation of concerns
    
    This service now acts as a facade that delegates to specialized components:
    - MultiTimeframeSignalEngine for advanced signal detection
    - Enhanced caching for performance
    - Specialized pool managers for different liquidity types
    """
    
    def __init__(self, repo: AlpacaCryptoRepository, redis_client: redis.Redis, db_session: Session):
        self.repo = repo
        self.redis = redis_client
        self.db = db_session
        
        # Initialize enhanced cache manager
        self.cache_manager = CacheManager(redis_client, use_memory_cache=True)
        
        # Initialize multi-timeframe engine
        self.mtf_engine = MultiTimeframeSignalEngine(repo, db_session, self.cache_manager)
    
    def _cache_key(self, symbol: str, timeframe: str, start: str, end: str) -> str:
        """Legacy cache key method - kept for backwards compatibility"""
        key_str = f"{symbol}-{timeframe}-{start}-{end}"
        return f"bars:{sha256(key_str.encode()).hexdigest()}"
    
    def detect_signals(
        self,
        symbol: str,
        signal_type: str,
        timeframe: str = "15Min",
        start: str = None,
        end: str = None,
    ) -> dict:
        """
        Legacy method for backwards compatibility
        
        For new implementations, use detect_multi_timeframe_signals()
        """
        # Use enhanced caching
        cached_candles = self.cache_manager.get_bars(symbol, timeframe, start, end)
        
        if cached_candles:
            print("✅ Using cached bars")
            candles = cached_candles
        else:
            print("📡 Fetching bars from Alpaca")
            bars: List[Candle] = self.repo.get_bars(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
            )
            # FIX: Ensure proper symbol and timeframe in candles
            candles = [
                {
                    **bar.dict(),
                    "symbol": symbol,
                    "timeframe": timeframe
                }
                for bar in bars
            ]
            self.cache_manager.set_bars(symbol, timeframe, start, end, candles)

        result = {
            "candles": candles,
            "tracked_fvgs": [],
            "pivots": [],
            "signals": []
        }

        if signal_type in ["pivot", "fvg_and_pivot"]:
            pivots = pivot_points.detect_pivots(candles)
            self.save_pivots(pivots, symbol, timeframe)
            result["candles"] = pivots
            result["pivots"] = [p for p in pivots if p.get("potential_swing_high") or p.get("potential_swing_low")]

        if signal_type in ["fvg", "fvg_and_pivot"]:
            # Use unified FVG management system
            from src.core.liquidity.unified_fvg_manager import UnifiedFVGManager
            
            unified_manager = UnifiedFVGManager(self.db)
            
            # Detect FVG zones using unified system
            zones = unified_manager.detect_fvg_zones(candles)
            
            # Update zones with current price action
            updated_zones = unified_manager.update_fvg_status(zones, candles)
            
            # Convert zones to legacy format for backward compatibility
            tracked_fvgs = []
            for zone in updated_zones:
                tracked_fvgs.append({
                    "fvg_id": zone.id,
                    "index": 0,  # Legacy field
                    "timestamp": zone.timestamp,
                    "zone": [zone.zone_low, zone.zone_high],
                    "direction": zone.direction,
                    "status": zone.status,
                    "invalidated_by": zone.invalidated_by_candle,
                    "mitigation_by": zone.last_touch_time,
                    "iFVG": False,  # Removed as requested
                    "retested": zone.touch_count > 1,
                    "retested_at": zone.last_touch_time,
                    "touch_count": zone.touch_count,
                    "max_penetration_pct": zone.max_penetration_pct,
                    "confidence": zone.confidence,
                    "strength": zone.strength
                })
            
            # Save zones to database (ONLY HTF TIMEFRAMES)
            if timeframe in ["4H", "1D"]:  # Only save HTF FVGs, avoid LTF pollution
                unified_manager.save_zones(updated_zones)
                print(f"✅ Saved {len(updated_zones)} {timeframe} FVGs to database")
            else:
                print(f"⚠️  Skipped saving {len(updated_zones)} {timeframe} FVGs (LTF not stored)")
            
            # Add FVG zone info to candles for backward compatibility
            detected_candles = []
            for i, candle in enumerate(candles):
                candle_copy = candle.copy()
                candle_copy["fvg_bullish"] = False
                candle_copy["fvg_bearish"] = False
                candle_copy["fvg_zone"] = None
                
                # Check if this candle has an FVG
                candle_time = candle["timestamp"]
                for zone in updated_zones:
                    if zone.timestamp.isoformat() == candle_time.replace("Z", "+00:00"):
                        candle_copy["fvg_bullish"] = zone.direction == "bullish"
                        candle_copy["fvg_bearish"] = zone.direction == "bearish"
                        candle_copy["fvg_zone"] = [zone.zone_low, zone.zone_high]
                        break
                
                detected_candles.append(candle_copy)
            
            result["candles"] = detected_candles
            result["tracked_fvgs"] = tracked_fvgs

        return result
    
    def detect_multi_timeframe_signals(
        self,
        symbol: str,
        strategy_type: str = "intraday",
        start: Optional[str] = None,
        end: Optional[str] = None,
        update_pools: bool = True
    ) -> List[TradingSignal]:
        """
        New method for advanced multi-timeframe signal detection
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USD")
            strategy_type: Strategy type (scalping, intraday, swing, position)
            start: Start time for analysis
            end: End time for analysis
            update_pools: Whether to update liquidity pools
            
        Returns:
            List of TradingSignal objects with comprehensive signal data
        """
        return self.mtf_engine.detect_signals(
            symbol=symbol,
            strategy_type=strategy_type,
            start=start,
            end=end,
            update_pools=update_pools
        )
    
    def get_liquidity_pools(self, symbol: str, timeframe: str, pool_type: str = "all") -> dict:
        """
        Get active liquidity pools for a symbol and timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., "4H", "1D")
            pool_type: Type of pools ("fvg", "pivot", "all")
            
        Returns:
            Dictionary with pool information
        """
        result = {}
        
        if pool_type in ["fvg", "all"]:
            fvg_pools = self.mtf_engine.fvg_manager.load_active_pools(symbol, timeframe)
            result["fvg_pools"] = [
                {
                    "id": pool.id,
                    "symbol": pool.symbol,
                    "timeframe": pool.timeframe,
                    "timestamp": pool.timestamp.isoformat(),
                    "zone_low": pool.zone_low,
                    "zone_high": pool.zone_high,
                    "direction": pool.direction,
                    "status": pool.status,
                    "strength": pool.strength,
                    "is_inverse": pool.is_inverse,
                    "touch_count": pool.touch_count
                }
                for pool in fvg_pools
            ]
        
        if pool_type in ["pivot", "all"]:
            pivot_pools = self.mtf_engine.pivot_manager.load_active_pools(symbol, timeframe)
            result["pivot_pools"] = [
                {
                    "id": pool.id,
                    "symbol": pool.symbol,
                    "timeframe": pool.timeframe,
                    "timestamp": pool.timestamp.isoformat(),
                    "price_level": pool.price_level,
                    "pivot_type": pool.pivot_type,
                    "status": pool.status,
                    "strength": pool.strength,
                    "confirmed": pool.confirmed,
                    "test_count": pool.test_count
                }
                for pool in pivot_pools
            ]
        
        return result
    
    def update_liquidity_pools(self, symbol: str, timeframe: str, start: str, end: str) -> dict:
        """
        Update liquidity pools for a symbol and timeframe
        
        Returns:
            Dictionary with update statistics
        """
        # Get fresh candle data
        candles = self._get_candles_with_cache(symbol, timeframe, start, end)
        
        # Update FVG pools
        fvg_pools = self.mtf_engine.fvg_manager.detect_pools(candles, symbol, timeframe)
        updated_fvg_pools = self.mtf_engine.fvg_manager.update_pool_status(fvg_pools, candles)
        
        try:
            fvg_saved = self.mtf_engine.fvg_manager.save_pools(updated_fvg_pools)
        except Exception as e:
            print(f"Error saving FVG pools: {e}")
            fvg_saved = False
        
        # Update pivot pools
        pivot_pools = self.mtf_engine.pivot_manager.detect_pools(candles, symbol, timeframe)
        updated_pivot_pools = self.mtf_engine.pivot_manager.update_pool_status(pivot_pools, candles)
        pivot_saved = self.mtf_engine.pivot_manager.save_pools(updated_pivot_pools)
        
        return {
            "fvg_pools_updated": len(updated_fvg_pools),
            "pivot_pools_updated": len(updated_pivot_pools),
            "fvg_save_success": fvg_saved,
            "pivot_save_success": pivot_saved,
            "candles_processed": len(candles)
        }
    
    def get_signal_history(self, symbol: Optional[str] = None, hours_back: int = 24) -> List[dict]:
        """
        Get signal history
        
        Args:
            symbol: Optional symbol filter
            hours_back: Hours to look back
            
        Returns:
            List of signal dictionaries
        """
        signals = self.mtf_engine.get_signal_history(symbol, hours_back)
        
        return [
            {
                "id": signal.id,
                "signal_type": signal.signal_type.value,
                "symbol": signal.symbol,
                "ltf_timeframe": signal.ltf_timeframe,
                "htf_timeframe": signal.htf_timeframe,
                "timestamp": signal.timestamp.isoformat(),
                "price": signal.price,
                "direction": signal.direction,
                "strength": signal.strength.value,
                "confidence": signal.confidence,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "htf_context": signal.htf_context,
                "ltf_context": signal.ltf_context,
                "related_pools": signal.related_pools,
                "expires_at": signal.expires_at.isoformat() if signal.expires_at else None
            }
            for signal in signals
        ]
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        return self.mtf_engine.get_cache_stats()
    
    def cleanup_old_data(self, days_old: int = 7) -> dict:
        """Clean up old data"""
        return self.mtf_engine.cleanup_old_data(days_old)
    
    def _get_candles_with_cache(self, symbol: str, timeframe: str, start: str, end: str) -> List[Dict]:
        """Get candles with caching"""
        cached_candles = self.cache_manager.get_bars(symbol, timeframe, start, end)
        
        if cached_candles:
            return cached_candles
        
        bars: List[Candle] = self.repo.get_bars(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        candles = [bar.dict() for bar in bars]
        self.cache_manager.set_bars(symbol, timeframe, start, end, candles)
        
        return candles

    def save_tracked_fvgs(self, tracked: List[dict], symbol: str, timeframe: str):
        """
        Save or update FVGs using unified system
        """
        from src.core.liquidity.unified_fvg_manager import UnifiedFVGManager, FVGZone, FVGStatus
        
        unified_manager = UnifiedFVGManager(self.db)
        
        # Convert tracked FVGs to zones
        zones = []
        for f in tracked:
            zone = FVGZone(
                id=f["fvg_id"],
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.fromisoformat(f["timestamp"].replace("Z", "+00:00")),
                direction=f["direction"],
                zone_low=f["zone"][0],
                zone_high=f["zone"][1],
                status=f["status"],
                touch_count=f.get("touch_count", 0),
                max_penetration_pct=f.get("max_penetration_pct", 0.0),
                confidence=f.get("confidence", 0.5),
                strength=f.get("strength", 0.5),
                last_touch_time=datetime.fromisoformat(f["retested_at"].replace("Z", "+00:00")) if f.get("retested_at") else None
            )
            zones.append(zone)
        
        # Save zones using unified manager
        unified_manager.save_zones(zones)

    def save_pivots(self, pivot_data: List[Dict], symbol: str, timeframe: str):
        for i, item in enumerate(pivot_data):
            if item.get("potential_swing_high"):
                pivot = Pivot(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=item["timestamp"],
                    price=item["high"],
                    index=i,
                    type="high"
                )
                self.db.add(pivot)
            elif item.get("potential_swing_low"):
                pivot = Pivot(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=item["timestamp"],
                    price=item["low"],
                    index=i,
                    type="low"
                )
                self.db.add(pivot)
        self.db.commit()
