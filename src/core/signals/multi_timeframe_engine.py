"""
Multi-Timeframe Signal Detection Engine

This module orchestrates the detection of trading signals across multiple timeframes.
It manages liquidity pools, market structure analysis, and signal generation for
algorithmic trading strategies.

Key Features:
- Multi-timeframe analysis (HTF for context, LTF for entries)
- Liquidity pool management (FVGs, pivots)
- Real-time signal detection
- Market structure analysis
- Signal strength scoring
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
import uuid
from enum import Enum

from src.core.liquidity.fvg_pool_manager import FVGPoolManager, FVGPool
from src.core.liquidity.pivot_pool_manager import PivotPoolManager, PivotPool
from src.infrastructure.cache.enhanced_cache_manager import CacheManager
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from sqlalchemy.orm import Session


class SignalType(Enum):
    """Types of trading signals"""
    FVG_RETEST = "fvg_retest"
    PIVOT_BOUNCE = "pivot_bounce"
    STRUCTURE_BREAK = "structure_break"
    INVERSE_FVG = "inverse_fvg"
    LIQUIDITY_GRAB = "liquidity_grab"


class SignalStrength(Enum):
    """Signal strength levels"""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4


@dataclass
class TradingSignal:
    """Unified trading signal structure"""
    id: str
    signal_type: SignalType
    symbol: str
    ltf_timeframe: str
    htf_timeframe: str
    timestamp: datetime
    price: float
    direction: str  # "bullish" or "bearish"
    strength: SignalStrength
    confidence: float  # 0.0 to 1.0
    
    # Context information
    htf_context: Dict = field(default_factory=dict)
    ltf_context: Dict = field(default_factory=dict)
    
    # Pool references
    related_pools: List[str] = field(default_factory=list)
    
    # Entry/Exit levels
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.expires_at is None:
            # Signals expire after 4 hours by default
            self.expires_at = self.created_at + timedelta(hours=4)


class MultiTimeframeSignalEngine:
    """Main engine for multi-timeframe signal detection"""
    
    def __init__(self, 
                 repo: AlpacaCryptoRepository,
                 db_session: Session,
                 cache_manager: CacheManager):
        self.repo = repo
        self.db = db_session
        self.cache = cache_manager
        
        # Initialize pool managers
        self.fvg_manager = FVGPoolManager(db_session, cache_manager)
        self.pivot_manager = PivotPoolManager(db_session, cache_manager)
        
        # Configuration
        self.signal_history: List[TradingSignal] = []
        self.max_signal_history = 1000
        
        # Timeframe configurations
        self.timeframe_configs = {
            "scalping": {"ltf": "5T", "htf": "1H"},
            "intraday": {"ltf": "15T", "htf": "4H"},
            "swing": {"ltf": "1H", "htf": "1D"},
            "position": {"ltf": "4H", "htf": "1W"}
        }
    
    def detect_signals(self, 
                      symbol: str,
                      strategy_type: str = "intraday",
                      start: Optional[str] = None,
                      end: Optional[str] = None,
                      update_pools: bool = True) -> List[TradingSignal]:
        """
        Main method to detect trading signals across timeframes
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USD")
            strategy_type: Strategy type (scalping, intraday, swing, position)
            start: Start time for analysis
            end: End time for analysis
            update_pools: Whether to update liquidity pools
            
        Returns:
            List of trading signals
        """
        config = self.timeframe_configs.get(strategy_type, self.timeframe_configs["intraday"])
        ltf = config["ltf"]
        htf = config["htf"]
        
        # Step 1: Load and update HTF context
        htf_context = self._load_htf_context(symbol, htf, start, end, update_pools)
        
        # Step 2: Load and update LTF data
        ltf_data = self._load_ltf_data(symbol, ltf, start, end, update_pools)
        
        # Step 3: Detect signals based on multi-timeframe analysis
        signals = []
        
        # FVG-based signals
        fvg_signals = self._detect_fvg_signals(symbol, ltf, htf, htf_context, ltf_data)
        signals.extend(fvg_signals)
        
        # Pivot-based signals
        pivot_signals = self._detect_pivot_signals(symbol, ltf, htf, htf_context, ltf_data)
        signals.extend(pivot_signals)
        
        # Structure break signals
        structure_signals = self._detect_structure_break_signals(symbol, ltf, htf, htf_context, ltf_data)
        signals.extend(structure_signals)
        
        # Step 4: Filter and rank signals
        filtered_signals = self._filter_and_rank_signals(signals)
        
        # Step 5: Update signal history
        self._update_signal_history(filtered_signals)
        
        return filtered_signals
    
    def _load_htf_context(self, symbol: str, htf: str, start: str, end: str, 
                         update_pools: bool) -> Dict:
        """Load HTF context including liquidity pools"""
        context = {
            "timeframe": htf,
            "fvg_pools": [],
            "pivot_pools": [],
            "market_structure": {},
            "candles": []
        }
        
        # Load HTF candles
        candles = self._get_candles(symbol, htf, start, end)
        context["candles"] = candles
        
        if update_pools:
            # Update FVG pools
            fvg_pools = self.fvg_manager.detect_pools(candles, symbol, htf)
            updated_fvg_pools = self.fvg_manager.update_pool_status(fvg_pools, candles)
            self.fvg_manager.save_pools(updated_fvg_pools)
            context["fvg_pools"] = updated_fvg_pools
            
            # Update pivot pools
            pivot_pools = self.pivot_manager.detect_pools(candles, symbol, htf)
            updated_pivot_pools = self.pivot_manager.update_pool_status(pivot_pools, candles)
            self.pivot_manager.save_pools(updated_pivot_pools)
            context["pivot_pools"] = updated_pivot_pools
        else:
            # Load existing pools
            context["fvg_pools"] = self.fvg_manager.load_active_pools(symbol, htf)
            context["pivot_pools"] = self.pivot_manager.load_active_pools(symbol, htf)
        
        # Analyze market structure
        context["market_structure"] = self._analyze_market_structure(candles, context["pivot_pools"])
        
        return context
    
    def _load_ltf_data(self, symbol: str, ltf: str, start: str, end: str,
                      update_pools: bool) -> Dict:
        """Load LTF data for signal detection"""
        data = {
            "timeframe": ltf,
            "candles": [],
            "fvg_pools": [],
            "pivot_pools": []
        }
        
        # Load LTF candles
        candles = self._get_candles(symbol, ltf, start, end)
        data["candles"] = candles
        
        if update_pools:
            # Detect local LTF pools
            fvg_pools = self.fvg_manager.detect_pools(candles, symbol, ltf)
            pivot_pools = self.pivot_manager.detect_pools(candles, symbol, ltf)
            
            data["fvg_pools"] = fvg_pools
            data["pivot_pools"] = pivot_pools
        
        return data
    
    def _detect_fvg_signals(self, symbol: str, ltf: str, htf: str,
                           htf_context: Dict, ltf_data: Dict) -> List[TradingSignal]:
        """Detect FVG-based signals"""
        signals = []
        
        # Get active HTF FVG pools
        htf_fvg_pools = [pool for pool in htf_context["fvg_pools"] if pool.status == "active"]
        
        # Check LTF candles for interaction with HTF FVGs
        for candle in ltf_data["candles"][-20:]:  # Check last 20 candles
            candle_time = datetime.fromisoformat(candle["timestamp"].replace("Z", "")).replace(tzinfo=timezone.utc)
            
            for fvg_pool in htf_fvg_pools:
                # Check if LTF candle is interacting with HTF FVG
                if self._is_price_near_fvg(candle, fvg_pool):
                    # Look for structure break in LTF
                    if self._detect_ltf_structure_shift(ltf_data["candles"], candle, fvg_pool.direction):
                        signal = TradingSignal(
                            id=f"fvg_signal_{uuid.uuid4().hex[:8]}",
                            signal_type=SignalType.FVG_RETEST,
                            symbol=symbol,
                            ltf_timeframe=ltf,
                            htf_timeframe=htf,
                            timestamp=candle_time,
                            price=candle["close"],
                            direction=fvg_pool.direction,
                            strength=self._calculate_signal_strength(fvg_pool, htf_context),
                            confidence=self._calculate_confidence(fvg_pool, candle, htf_context),
                            htf_context={"fvg_pool": fvg_pool.id},
                            ltf_context={"trigger_candle": candle["timestamp"]},
                            related_pools=[fvg_pool.id]
                        )
                        
                        # Set entry levels
                        signal.entry_price = candle["close"]
                        signal.stop_loss = self._calculate_stop_loss(signal, fvg_pool)
                        signal.take_profit = self._calculate_take_profit(signal, fvg_pool)
                        
                        signals.append(signal)
        
        return signals
    
    def _detect_pivot_signals(self, symbol: str, ltf: str, htf: str,
                             htf_context: Dict, ltf_data: Dict) -> List[TradingSignal]:
        """Detect pivot-based signals"""
        signals = []
        
        # Get significant HTF pivots
        htf_pivots = self.pivot_manager.get_significant_pivots(symbol, htf, min_strength=0.7)
        
        # Check for pivot bounces in LTF
        for candle in ltf_data["candles"][-20:]:
            candle_time = datetime.fromisoformat(candle["timestamp"].replace("Z", "")).replace(tzinfo=timezone.utc)
            current_price = candle["close"]
            
            # Get nearest pivots
            nearest_pivots = self.pivot_manager.get_nearest_pivots(symbol, htf, current_price)
            
            for pivot_list in [nearest_pivots["resistance_above"], nearest_pivots["support_below"]]:
                for pivot in pivot_list[:2]:  # Check top 2 nearest pivots
                    if self._is_pivot_bounce(candle, pivot, ltf_data["candles"]):
                        direction = "bearish" if pivot.pivot_type == "high" else "bullish"
                        
                        signal = TradingSignal(
                            id=f"pivot_signal_{uuid.uuid4().hex[:8]}",
                            signal_type=SignalType.PIVOT_BOUNCE,
                            symbol=symbol,
                            ltf_timeframe=ltf,
                            htf_timeframe=htf,
                            timestamp=candle_time,
                            price=current_price,
                            direction=direction,
                            strength=self._calculate_signal_strength(pivot, htf_context),
                            confidence=self._calculate_confidence(pivot, candle, htf_context),
                            htf_context={"pivot_pool": pivot.id},
                            ltf_context={"trigger_candle": candle["timestamp"]},
                            related_pools=[pivot.id]
                        )
                        
                        signal.entry_price = current_price
                        signal.stop_loss = self._calculate_stop_loss(signal, pivot)
                        signal.take_profit = self._calculate_take_profit(signal, pivot)
                        
                        signals.append(signal)
        
        return signals
    
    def _detect_structure_break_signals(self, symbol: str, ltf: str, htf: str,
                                       htf_context: Dict, ltf_data: Dict) -> List[TradingSignal]:
        """Detect structure break signals"""
        signals = []
        
        # Analyze recent LTF candles for structure breaks
        recent_candles = ltf_data["candles"][-50:]  # Last 50 candles
        
        # Make sure we have enough candles for analysis
        if len(recent_candles) < 20:
            return signals
        
        # Analyze the last 10 candles, but ensure we don't go out of bounds
        start_idx = max(10, len(recent_candles) - 10)  # Ensure at least 10 candles for lookback
        
        for i in range(start_idx, len(recent_candles)):
            candle = recent_candles[i]
            
            # Check for bullish structure break
            if self._is_bullish_structure_break(recent_candles, i):
                signal = TradingSignal(
                    id=f"structure_break_{uuid.uuid4().hex[:8]}",
                    signal_type=SignalType.STRUCTURE_BREAK,
                    symbol=symbol,
                    ltf_timeframe=ltf,
                    htf_timeframe=htf,
                    timestamp=datetime.fromisoformat(candle["timestamp"].replace("Z", "")).replace(tzinfo=timezone.utc),
                    price=candle["close"],
                    direction="bullish",
                    strength=SignalStrength.MODERATE,
                    confidence=0.7,
                    ltf_context={"break_candle": candle["timestamp"]},
                    htf_context=htf_context["market_structure"]
                )
                signals.append(signal)
            
            # Check for bearish structure break
            elif self._is_bearish_structure_break(recent_candles, i):
                signal = TradingSignal(
                    id=f"structure_break_{uuid.uuid4().hex[:8]}",
                    signal_type=SignalType.STRUCTURE_BREAK,
                    symbol=symbol,
                    ltf_timeframe=ltf,
                    htf_timeframe=htf,
                    timestamp=datetime.fromisoformat(candle["timestamp"].replace("Z", "")).replace(tzinfo=timezone.utc),
                    price=candle["close"],
                    direction="bearish",
                    strength=SignalStrength.MODERATE,
                    confidence=0.7,
                    ltf_context={"break_candle": candle["timestamp"]},
                    htf_context=htf_context["market_structure"]
                )
                signals.append(signal)
        
        return signals
    
    def _get_candles(self, symbol: str, timeframe: str, start: str, end: str) -> List[Dict]:
        """Get candles with caching"""
        cached_candles = self.cache.get_bars(symbol, timeframe, start, end)
        
        if cached_candles:
            return cached_candles
        
        # Fetch from data source
        bars = self.repo.get_bars(symbol=symbol, timeframe=timeframe, start=start, end=end)
        candles = [bar.dict() for bar in bars]
        
        # Cache the result
        self.cache.set_bars(symbol, timeframe, start, end, candles)
        
        return candles
    
    def _analyze_market_structure(self, candles: List[Dict], pivot_pools: List[PivotPool]) -> Dict:
        """Analyze market structure from candles and pivots"""
        # Simplified market structure analysis
        # This can be expanded with more sophisticated analysis
        
        if not pivot_pools:
            return {"trend": "unclear", "phase": "consolidation"}
        
        # Get recent pivots
        recent_pivots = sorted(pivot_pools, key=lambda p: p.timestamp)[-10:]
        
        # Simple trend analysis
        highs = [p for p in recent_pivots if p.pivot_type == "high"]
        lows = [p for p in recent_pivots if p.pivot_type == "low"]
        
        if len(highs) >= 2 and len(lows) >= 2:
            recent_highs = sorted(highs, key=lambda p: p.timestamp)[-2:]
            recent_lows = sorted(lows, key=lambda p: p.timestamp)[-2:]
            
            if (recent_highs[1].price_level > recent_highs[0].price_level and
                recent_lows[1].price_level > recent_lows[0].price_level):
                return {"trend": "bullish", "phase": "trending"}
            elif (recent_highs[1].price_level < recent_highs[0].price_level and
                  recent_lows[1].price_level < recent_lows[0].price_level):
                return {"trend": "bearish", "phase": "trending"}
        
        return {"trend": "neutral", "phase": "consolidation"}
    
    def _is_price_near_fvg(self, candle: Dict, fvg_pool: FVGPool) -> bool:
        """Check if price is near FVG zone"""
        high = candle["high"]
        low = candle["low"]
        
        # Check if candle overlaps with FVG zone
        return not (high < fvg_pool.zone_low or low > fvg_pool.zone_high)
    
    def _detect_ltf_structure_shift(self, candles: List[Dict], trigger_candle: Dict, 
                                   expected_direction: str) -> bool:
        """Detect structure shift in LTF that aligns with HTF expectation"""
        # Simplified structure shift detection
        # This can be enhanced with more sophisticated analysis
        
        trigger_idx = next((i for i, c in enumerate(candles) if c["timestamp"] == trigger_candle["timestamp"]), -1)
        
        if trigger_idx < 5:
            return False
        
        # Check for price movement in expected direction
        recent_candles = candles[trigger_idx-5:trigger_idx+1]
        
        if expected_direction == "bullish":
            return trigger_candle["close"] > max(c["high"] for c in recent_candles[:-1])
        else:
            return trigger_candle["close"] < min(c["low"] for c in recent_candles[:-1])
    
    def _is_pivot_bounce(self, candle: Dict, pivot: PivotPool, candles: List[Dict]) -> bool:
        """Check if candle represents a bounce from pivot level"""
        # Simplified bounce detection
        tolerance = 0.002  # 0.2% tolerance
        
        if pivot.pivot_type == "high":
            # Check for rejection from resistance
            return (candle["high"] >= pivot.price_level * (1 - tolerance) and
                    candle["close"] < candle["high"] * 0.95)
        else:
            # Check for bounce from support
            return (candle["low"] <= pivot.price_level * (1 + tolerance) and
                    candle["close"] > candle["low"] * 1.05)
    
    def _is_bullish_structure_break(self, candles: List[Dict], index: int) -> bool:
        """Check for bullish structure break"""
        if index < 10:
            return False
        
        current_candle = candles[index]
        lookback_candles = candles[index-10:index]
        
        # Find recent swing high
        swing_high = max(c["high"] for c in lookback_candles)
        
        # Check if current candle breaks above swing high
        return current_candle["close"] > swing_high
    
    def _is_bearish_structure_break(self, candles: List[Dict], index: int) -> bool:
        """Check for bearish structure break"""
        if index < 10:
            return False
        
        current_candle = candles[index]
        lookback_candles = candles[index-10:index]
        
        # Find recent swing low
        swing_low = min(c["low"] for c in lookback_candles)
        
        # Check if current candle breaks below swing low
        return current_candle["close"] < swing_low
    
    def _calculate_signal_strength(self, pool: Any, context: Dict) -> SignalStrength:
        """Calculate signal strength based on pool and context"""
        if hasattr(pool, 'strength'):
            if pool.strength >= 0.8:
                return SignalStrength.VERY_STRONG
            elif pool.strength >= 0.6:
                return SignalStrength.STRONG
            elif pool.strength >= 0.4:
                return SignalStrength.MODERATE
            else:
                return SignalStrength.WEAK
        
        return SignalStrength.MODERATE
    
    def _calculate_confidence(self, pool: Any, candle: Dict, context: Dict) -> float:
        """Calculate signal confidence score"""
        base_confidence = 0.5
        
        # Factor in pool strength
        if hasattr(pool, 'strength'):
            base_confidence += pool.strength * 0.3
        
        # Factor in market structure alignment
        if context.get("market_structure", {}).get("trend") != "unclear":
            base_confidence += 0.1
        
        # Factor in confluence (multiple pools nearby)
        # This can be enhanced with more sophisticated analysis
        
        return min(base_confidence, 1.0)
    
    def _calculate_stop_loss(self, signal: TradingSignal, pool: Any) -> float:
        """Calculate stop loss level"""
        # Simplified stop loss calculation
        if signal.direction == "bullish":
            if hasattr(pool, 'zone_low'):
                return pool.zone_low * 0.999  # Just below FVG
            else:
                return pool.price_level * 0.995  # Just below pivot
        else:
            if hasattr(pool, 'zone_high'):
                return pool.zone_high * 1.001  # Just above FVG
            else:
                return pool.price_level * 1.005  # Just above pivot
    
    def _calculate_take_profit(self, signal: TradingSignal, pool: Any) -> float:
        """Calculate take profit level"""
        # Simplified take profit calculation - can be enhanced
        risk = abs(signal.entry_price - signal.stop_loss) if signal.stop_loss else signal.entry_price * 0.01
        reward_ratio = 2.0  # 2:1 reward to risk ratio
        
        if signal.direction == "bullish":
            return signal.entry_price + (risk * reward_ratio)
        else:
            return signal.entry_price - (risk * reward_ratio)
    
    def _filter_and_rank_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """Filter and rank signals by quality"""
        # Remove expired signals
        now = datetime.now(timezone.utc)
        active_signals = [s for s in signals if s.expires_at > now]
        
        # Remove duplicate signals (same symbol, type, direction within short time)
        filtered_signals = []
        for signal in active_signals:
            is_duplicate = False
            for existing in filtered_signals:
                if (signal.symbol == existing.symbol and
                    signal.signal_type == existing.signal_type and
                    signal.direction == existing.direction and
                    abs((signal.timestamp - existing.timestamp).total_seconds()) < 3600):  # 1 hour window
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_signals.append(signal)
        
        # Sort by strength and confidence
        filtered_signals.sort(key=lambda s: (s.strength.value, s.confidence), reverse=True)
        
        return filtered_signals[:20]  # Return top 20 signals
    
    def _update_signal_history(self, signals: List[TradingSignal]) -> None:
        """Update signal history"""
        self.signal_history.extend(signals)
        
        # Keep only recent signals
        if len(self.signal_history) > self.max_signal_history:
            self.signal_history = self.signal_history[-self.max_signal_history:]
    
    def get_signal_history(self, symbol: Optional[str] = None, 
                          hours_back: int = 24) -> List[TradingSignal]:
        """Get signal history"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        filtered_history = [
            s for s in self.signal_history 
            if s.timestamp >= cutoff_time
        ]
        
        if symbol:
            filtered_history = [s for s in filtered_history if s.symbol == symbol]
        
        return filtered_history
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return self.cache.get_cache_stats()
    
    def cleanup_old_data(self, days_old: int = 7) -> Dict:
        """Clean up old data"""
        cleanup_stats = {
            "fvg_pools_removed": self.fvg_manager.cleanup_old_pools("", "", days_old),
            "pivot_pools_removed": self.pivot_manager.cleanup_old_pools("", "", days_old),
            "cache_entries_cleaned": self.cache.cleanup_expired()
        }
        
        return cleanup_stats
