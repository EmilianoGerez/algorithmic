"""
Market Context Evaluators

Evaluates market context at the time of liquidity pool interactions
"""

import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from ..composable_strategy import ContextEvaluator, MarketContext, LiquidityPoolEvent, TrendDirection


class BasicMarketContextEvaluator(ContextEvaluator):
    """Basic market context evaluator focusing on trend, volume, and volatility"""
    
    def __init__(self, volume_lookback: int = 20, volatility_lookback: int = 20):
        """
        Initialize basic market context evaluator
        
        Args:
            volume_lookback: Number of candles to look back for volume analysis
            volatility_lookback: Number of candles to look back for volatility analysis
        """
        self.volume_lookback = volume_lookback
        self.volatility_lookback = volatility_lookback
    
    def evaluate_context(self, candles: List[Dict], event: LiquidityPoolEvent) -> MarketContext:
        """
        Evaluate market context at the time of liquidity pool event
        
        Args:
            candles: List of OHLCV candles
            event: Liquidity pool event
        
        Returns:
            MarketContext with analysis
        """
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Find the candle closest to the event time
            event_idx = self._find_event_candle_index(df, event.timestamp)
            
            if event_idx is None:
                event_idx = len(df) - 1  # Use last candle if not found
            
            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(df, event_idx)
            
            # Analyze trend regime
            trend_regime = self._analyze_trend_regime(df, event_idx)
            
            # Analyze market structure
            market_structure = self._analyze_market_structure(df, event_idx)
            
            # Calculate volatility
            volatility = self._calculate_volatility(df, event_idx)
            
            # Analyze absorption (simplified)
            absorption_level = self._analyze_absorption(df, event_idx)
            
            # Detect exhaustion signals
            exhaustion_signals = self._detect_exhaustion_signals(df, event_idx)
            
            return MarketContext(
                timestamp=event.timestamp,
                volume_profile=volume_profile,
                trend_regime=trend_regime,
                market_structure=market_structure,
                volatility=volatility,
                absorption_level=absorption_level,
                exhaustion_signals=exhaustion_signals,
                metadata={
                    "event_candle_index": event_idx,
                    "total_candles": len(df),
                    "analysis_window": min(self.volume_lookback, event_idx + 1)
                }
            )
            
        except Exception as e:
            print(f"Error in market context evaluation: {e}")
            # Return basic context
            return MarketContext(
                timestamp=event.timestamp,
                volume_profile={"avg_volume": 0, "relative_volume": 1.0},
                trend_regime=TrendDirection.NEUTRAL,
                market_structure="unknown",
                volatility=0.0,
                absorption_level=0.5,
                exhaustion_signals=[],
                metadata={"error": str(e)}
            )
    
    def _find_event_candle_index(self, df: pd.DataFrame, event_time: datetime) -> Optional[int]:
        """Find the index of the candle closest to the event time"""
        
        # Convert event time to pandas datetime and make timezone-aware if needed
        event_time_pd = pd.to_datetime(event_time)
        
        # Make sure both timestamps are timezone-aware or both are naive
        if event_time_pd.tz is None and df['timestamp'].dt.tz is not None:
            event_time_pd = event_time_pd.tz_localize('UTC')
        elif event_time_pd.tz is not None and df['timestamp'].dt.tz is None:
            event_time_pd = event_time_pd.tz_localize(None)
        
        # Find the closest candle
        try:
            time_diffs = abs(df['timestamp'] - event_time_pd)
            closest_idx = time_diffs.idxmin()
            return closest_idx
        except Exception as e:
            print(f"Error finding event candle: {e}")
            return len(df) - 1  # Return last candle as fallback
    
    def _analyze_volume_profile(self, df: pd.DataFrame, event_idx: int) -> Dict[str, float]:
        """Analyze volume profile around the event"""
        
        # Get volume data
        start_idx = max(0, event_idx - self.volume_lookback + 1)
        volume_window = df.iloc[start_idx:event_idx + 1]['volume']
        
        if len(volume_window) == 0:
            return {"avg_volume": 0, "relative_volume": 1.0, "volume_trend": 0.0}
        
        # Calculate average volume
        avg_volume = volume_window.mean()
        
        # Current volume relative to average
        current_volume = df.iloc[event_idx]['volume']
        relative_volume = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Volume trend (recent vs older)
        if len(volume_window) >= 4:
            recent_avg = volume_window.tail(3).mean()
            older_avg = volume_window.head(len(volume_window) - 3).mean()
            volume_trend = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0.0
        else:
            volume_trend = 0.0
        
        return {
            "avg_volume": avg_volume,
            "relative_volume": relative_volume,
            "volume_trend": volume_trend,
            "current_volume": current_volume
        }
    
    def _analyze_trend_regime(self, df: pd.DataFrame, event_idx: int) -> TrendDirection:
        """Analyze trend regime using simple moving averages"""
        
        # Use 20-period SMA for trend analysis
        sma_period = min(20, event_idx + 1)
        
        if sma_period < 5:
            return TrendDirection.NEUTRAL
        
        # Calculate SMA
        start_idx = max(0, event_idx - sma_period + 1)
        price_window = df.iloc[start_idx:event_idx + 1]['close']
        sma = price_window.mean()
        
        current_price = df.iloc[event_idx]['close']
        
        # Simple trend determination
        if current_price > sma * 1.005:  # 0.5% above SMA
            return TrendDirection.BULLISH
        elif current_price < sma * 0.995:  # 0.5% below SMA
            return TrendDirection.BEARISH
        else:
            return TrendDirection.NEUTRAL
    
    def _analyze_market_structure(self, df: pd.DataFrame, event_idx: int) -> str:
        """Analyze market structure (ranging, trending, breakout)"""
        
        # Look at recent price action
        lookback = min(10, event_idx + 1)
        start_idx = max(0, event_idx - lookback + 1)
        price_window = df.iloc[start_idx:event_idx + 1]
        
        if len(price_window) < 3:
            return "insufficient_data"
        
        # Calculate price range
        high_price = price_window['high'].max()
        low_price = price_window['low'].min()
        price_range = high_price - low_price
        
        # Calculate average true range
        atr = self._calculate_atr(price_window)
        
        # Determine structure
        if price_range < atr * 2:
            return "ranging"
        elif price_range > atr * 5:
            return "trending"
        else:
            return "transitional"
    
    def _calculate_volatility(self, df: pd.DataFrame, event_idx: int) -> float:
        """Calculate volatility using ATR"""
        
        lookback = min(self.volatility_lookback, event_idx + 1)
        start_idx = max(0, event_idx - lookback + 1)
        price_window = df.iloc[start_idx:event_idx + 1]
        
        return self._calculate_atr(price_window)
    
    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """Calculate Average True Range"""
        
        if len(df) < 2:
            return 0.0
        
        # Calculate True Range
        df = df.copy()
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        
        # Return average
        return df['true_range'].mean()
    
    def _analyze_absorption(self, df: pd.DataFrame, event_idx: int) -> float:
        """Analyze absorption level (simplified)"""
        
        # Look at recent volume vs price movement
        lookback = min(5, event_idx + 1)
        start_idx = max(0, event_idx - lookback + 1)
        recent_candles = df.iloc[start_idx:event_idx + 1]
        
        if len(recent_candles) < 2:
            return 0.5
        
        # Calculate volume-weighted price movement
        total_volume = recent_candles['volume'].sum()
        if total_volume == 0:
            return 0.5
        
        # Simple absorption metric: high volume with low price movement = high absorption
        price_movement = abs(recent_candles['close'].iloc[-1] - recent_candles['close'].iloc[0])
        avg_volume = recent_candles['volume'].mean()
        
        # Normalize to 0-1 scale
        if price_movement == 0:
            return 1.0
        
        absorption = min(1.0, avg_volume / (price_movement * 1000))  # Scaled for typical crypto prices
        
        return absorption
    
    def _detect_exhaustion_signals(self, df: pd.DataFrame, event_idx: int) -> List[str]:
        """Detect exhaustion signals"""
        
        exhaustion_signals = []
        
        # Look at recent candles
        lookback = min(3, event_idx + 1)
        start_idx = max(0, event_idx - lookback + 1)
        recent_candles = df.iloc[start_idx:event_idx + 1]
        
        if len(recent_candles) < 2:
            return exhaustion_signals
        
        # Check for volume exhaustion
        if len(recent_candles) >= 2:
            last_volume = recent_candles['volume'].iloc[-1]
            prev_volume = recent_candles['volume'].iloc[-2]
            
            if last_volume < prev_volume * 0.5:  # 50% volume drop
                exhaustion_signals.append("volume_exhaustion")
        
        # Check for price exhaustion (long wicks)
        last_candle = recent_candles.iloc[-1]
        body_size = abs(last_candle['close'] - last_candle['open'])
        total_size = last_candle['high'] - last_candle['low']
        
        if total_size > 0 and body_size / total_size < 0.3:  # Small body, large wicks
            exhaustion_signals.append("price_exhaustion")
        
        # Check for momentum exhaustion (decreasing momentum)
        if len(recent_candles) >= 3:
            momentum_decreasing = True
            for i in range(1, len(recent_candles)):
                current_move = abs(recent_candles['close'].iloc[i] - recent_candles['open'].iloc[i])
                prev_move = abs(recent_candles['close'].iloc[i-1] - recent_candles['open'].iloc[i-1])
                
                if current_move >= prev_move:
                    momentum_decreasing = False
                    break
            
            if momentum_decreasing:
                exhaustion_signals.append("momentum_exhaustion")
        
        return exhaustion_signals
