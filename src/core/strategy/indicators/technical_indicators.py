"""
EMA Crossover Technical Indicator

Implements the EMA crossover strategy for entry signal confirmation
"""

import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from ..composable_strategy import TechnicalIndicator, TechnicalSignal, TrendDirection, SignalStrength, MarketContext


class EMACrossoverIndicator(TechnicalIndicator):
    """EMA Crossover technical indicator for entry confirmation"""
    
    def __init__(self, fast_period: int = 9, slow_period: int = 20, 
                 lookback_candles: int = 5, min_separation: float = 0.001):
        """
        Initialize EMA crossover indicator
        
        Args:
            fast_period: Period for fast EMA (default: 9)
            slow_period: Period for slow EMA (default: 20)
            lookback_candles: Number of candles to look back for crossover (default: 5)
            min_separation: Minimum separation between EMAs to avoid noise (default: 0.1%)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.lookback_candles = lookback_candles
        self.min_separation = min_separation
    
    def generate_signal(self, candles: List[Dict], context: MarketContext) -> Optional[TechnicalSignal]:
        """
        Generate EMA crossover signal
        
        Args:
            candles: List of OHLCV candles
            context: Market context for additional filtering
        
        Returns:
            TechnicalSignal if crossover detected, None otherwise
        """
        
        if len(candles) < max(self.fast_period, self.slow_period) + self.lookback_candles:
            return None
        
        try:
            # Convert to DataFrame for easier calculation
            df = pd.DataFrame(candles)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate EMAs
            df['ema_fast'] = df['close'].ewm(span=self.fast_period).mean()
            df['ema_slow'] = df['close'].ewm(span=self.slow_period).mean()
            
            # Calculate EMA difference and percentage separation
            df['ema_diff'] = df['ema_fast'] - df['ema_slow']
            df['ema_separation'] = abs(df['ema_diff']) / df['close']
            
            # Check for crossover in recent candles
            crossover_info = self._detect_crossover(df)
            
            if crossover_info:
                direction, strength, confidence, signal_timestamp = crossover_info
                
                # Get latest EMA values
                latest_idx = len(df) - 1
                latest_ema_fast = df.iloc[latest_idx]['ema_fast']
                latest_ema_slow = df.iloc[latest_idx]['ema_slow']
                latest_price = df.iloc[latest_idx]['close']
                
                # Create technical signal
                return TechnicalSignal(
                    signal_type="ema_crossover",
                    timestamp=signal_timestamp,
                    direction=direction,
                    strength=strength,
                    confidence=confidence,
                    values={
                        "ema_fast": latest_ema_fast,
                        "ema_slow": latest_ema_slow,
                        "current_price": latest_price,
                        "ema_diff": latest_ema_fast - latest_ema_slow,
                        "separation_pct": abs(latest_ema_fast - latest_ema_slow) / latest_price
                    },
                    metadata={
                        "fast_period": self.fast_period,
                        "slow_period": self.slow_period,
                        "crossover_candles_ago": crossover_info[4] if len(crossover_info) > 4 else 0
                    }
                )
            
            return None
            
        except Exception as e:
            print(f"Error in EMA crossover calculation: {e}")
            return None
    
    def _detect_crossover(self, df: pd.DataFrame) -> Optional[tuple]:
        """
        Detect EMA crossover in recent candles
        
        Args:
            df: DataFrame with EMA calculations
        
        Returns:
            Tuple of (direction, strength, confidence, timestamp, candles_ago) if crossover detected
        """
        
        # Look at recent candles for crossover
        recent_df = df.tail(self.lookback_candles + 1)
        
        crossover_detected = False
        crossover_direction = None
        crossover_idx = None
        
        # Check each candle for crossover
        for i in range(1, len(recent_df)):
            current_row = recent_df.iloc[i]
            previous_row = recent_df.iloc[i-1]
            
            # Check for bullish crossover (fast EMA crosses above slow EMA)
            if (previous_row['ema_fast'] <= previous_row['ema_slow'] and 
                current_row['ema_fast'] > current_row['ema_slow']):
                
                # Verify minimum separation to avoid noise
                if current_row['ema_separation'] >= self.min_separation:
                    crossover_detected = True
                    crossover_direction = TrendDirection.BULLISH
                    crossover_idx = i
                    break
            
            # Check for bearish crossover (fast EMA crosses below slow EMA)
            elif (previous_row['ema_fast'] >= previous_row['ema_slow'] and 
                  current_row['ema_fast'] < current_row['ema_slow']):
                
                # Verify minimum separation to avoid noise
                if current_row['ema_separation'] >= self.min_separation:
                    crossover_detected = True
                    crossover_direction = TrendDirection.BEARISH
                    crossover_idx = i
                    break
        
        if not crossover_detected:
            return None
        
        # Calculate signal strength and confidence
        crossover_row = recent_df.iloc[crossover_idx]
        
        # Strength based on EMA separation
        separation_pct = crossover_row['ema_separation']
        if separation_pct >= 0.005:  # 0.5%
            strength = SignalStrength.STRONG
        elif separation_pct >= 0.002:  # 0.2%
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.WEAK
        
        # Confidence based on consistency of EMA direction after crossover
        confidence = self._calculate_confidence(recent_df, crossover_idx, crossover_direction)
        
        # Get timestamp
        signal_timestamp = crossover_row['timestamp']
        
        # Calculate how many candles ago the crossover occurred
        candles_ago = len(recent_df) - crossover_idx - 1
        
        return (crossover_direction, strength, confidence, signal_timestamp, candles_ago)
    
    def _calculate_confidence(self, df: pd.DataFrame, crossover_idx: int, direction: TrendDirection) -> float:
        """
        Calculate confidence based on EMA behavior after crossover
        
        Args:
            df: DataFrame with EMA data
            crossover_idx: Index of crossover candle
            direction: Direction of crossover
        
        Returns:
            Confidence score (0-1)
        """
        
        # Start with base confidence
        confidence = 0.6
        
        # Check if EMAs continue in the right direction after crossover
        consistency_bonus = 0.0
        separation_bonus = 0.0
        
        for i in range(crossover_idx + 1, len(df)):
            current_row = df.iloc[i]
            
            # Check direction consistency
            if direction == TrendDirection.BULLISH:
                if current_row['ema_fast'] > current_row['ema_slow']:
                    consistency_bonus += 0.1
                else:
                    consistency_bonus -= 0.05
            else:  # BEARISH
                if current_row['ema_fast'] < current_row['ema_slow']:
                    consistency_bonus += 0.1
                else:
                    consistency_bonus -= 0.05
            
            # Check if separation is increasing (stronger signal)
            if i > crossover_idx + 1:
                prev_row = df.iloc[i-1]
                if current_row['ema_separation'] > prev_row['ema_separation']:
                    separation_bonus += 0.05
        
        # Apply bonuses
        confidence += consistency_bonus
        confidence += separation_bonus
        
        # Clamp between 0 and 1
        return max(0.0, min(1.0, confidence))


class RSIDivergenceIndicator(TechnicalIndicator):
    """RSI Divergence indicator for additional confirmation"""
    
    def __init__(self, period: int = 14, lookback_candles: int = 10, 
                 overbought: float = 70, oversold: float = 30):
        """
        Initialize RSI divergence indicator
        
        Args:
            period: RSI period (default: 14)
            lookback_candles: Candles to look back for divergence (default: 10)
            overbought: Overbought threshold (default: 70)
            oversold: Oversold threshold (default: 30)
        """
        self.period = period
        self.lookback_candles = lookback_candles
        self.overbought = overbought
        self.oversold = oversold
    
    def generate_signal(self, candles: List[Dict], context: MarketContext) -> Optional[TechnicalSignal]:
        """
        Generate RSI divergence signal
        
        Args:
            candles: List of OHLCV candles
            context: Market context
        
        Returns:
            TechnicalSignal if divergence detected, None otherwise
        """
        
        if len(candles) < self.period + self.lookback_candles:
            return None
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate RSI
            df['rsi'] = self._calculate_rsi(df['close'], self.period)
            
            # Look for divergence patterns
            divergence_info = self._detect_divergence(df)
            
            if divergence_info:
                direction, strength, confidence, signal_timestamp = divergence_info
                
                # Get latest RSI value
                latest_rsi = df.iloc[-1]['rsi']
                
                return TechnicalSignal(
                    signal_type="rsi_divergence",
                    timestamp=signal_timestamp,
                    direction=direction,
                    strength=strength,
                    confidence=confidence,
                    values={
                        "rsi": latest_rsi,
                        "overbought": self.overbought,
                        "oversold": self.oversold
                    },
                    metadata={
                        "period": self.period,
                        "divergence_type": divergence_info[4] if len(divergence_info) > 4 else "regular"
                    }
                )
            
            return None
            
        except Exception as e:
            print(f"Error in RSI divergence calculation: {e}")
            return None
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _detect_divergence(self, df: pd.DataFrame) -> Optional[tuple]:
        """
        Detect RSI divergence patterns
        
        Args:
            df: DataFrame with price and RSI data
        
        Returns:
            Tuple of (direction, strength, confidence, timestamp, type) if divergence detected
        """
        
        # Look at recent data
        recent_df = df.tail(self.lookback_candles)
        
        # Find local highs and lows in both price and RSI
        price_highs = []
        price_lows = []
        rsi_highs = []
        rsi_lows = []
        
        for i in range(1, len(recent_df) - 1):
            current = recent_df.iloc[i]
            prev = recent_df.iloc[i-1]
            next_row = recent_df.iloc[i+1]
            
            # Price highs/lows
            if current['high'] > prev['high'] and current['high'] > next_row['high']:
                price_highs.append((i, current['high']))
            if current['low'] < prev['low'] and current['low'] < next_row['low']:
                price_lows.append((i, current['low']))
            
            # RSI highs/lows
            if current['rsi'] > prev['rsi'] and current['rsi'] > next_row['rsi']:
                rsi_highs.append((i, current['rsi']))
            if current['rsi'] < prev['rsi'] and current['rsi'] < next_row['rsi']:
                rsi_lows.append((i, current['rsi']))
        
        # Check for bullish divergence (price lows, RSI highs)
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            # Price making lower lows, RSI making higher lows
            if (price_lows[-1][1] < price_lows[-2][1] and 
                rsi_lows[-1][1] > rsi_lows[-2][1]):
                
                return (TrendDirection.BULLISH, SignalStrength.MEDIUM, 0.7, 
                       recent_df.iloc[-1]['timestamp'], "bullish_divergence")
        
        # Check for bearish divergence (price highs, RSI lows)
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            # Price making higher highs, RSI making lower highs
            if (price_highs[-1][1] > price_highs[-2][1] and 
                rsi_highs[-1][1] < rsi_highs[-2][1]):
                
                return (TrendDirection.BEARISH, SignalStrength.MEDIUM, 0.7, 
                       recent_df.iloc[-1]['timestamp'], "bearish_divergence")
        
        return None
