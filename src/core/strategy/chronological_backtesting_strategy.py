#!/usr/bin/env python3
"""
Chronological Backtesting Strategy
Simulates real-time processing to avoid data leakage
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
from src.core.strategy.composable_strategy import ComposableStrategy, EntrySignal
from src.core.strategy.detectors.liquidity_pool_detectors import FVGPoolDetector
from src.core.strategy.indicators.technical_indicators import EMACrossoverIndicator
from src.core.strategy.evaluators.market_context_evaluators import BasicMarketContextEvaluator
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


class ChronologicalBacktestingStrategy(ComposableStrategy):
    """
    Strategy that processes data chronologically to avoid data leakage
    Simulates real-time processing by only using information available at each timestamp
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        super().__init__(self.config)
        
        # Strategy configuration
        self.ema_fast_period = self.config.get("ema_fast_period", 9)
        self.ema_slow_period = self.config.get("ema_slow_period", 20)
        self.swing_lookback_candles = self.config.get("swing_lookback_candles", 3)
        self.confirmation_window_hours = self.config.get("confirmation_window_hours", 12)
        self.min_confidence = self.config.get("min_confidence_threshold", 0.6)
        self.htf_lookback_hours = self.config.get("htf_lookback_hours", 720)  # 30 days
        
        # Initialize components
        self.fvg_detector = FVGPoolDetector()
        self.ema_indicator = EMACrossoverIndicator(self.ema_fast_period, self.ema_slow_period)
        self.context_evaluator = BasicMarketContextEvaluator()
        
        # Initialize data service
        repo = AlpacaCryptoRepository()
        redis = get_redis_connection()
        db = SessionLocal()
        self.data_service = SignalDetectionService(repo, redis, db)
    
    def backtest_chronological(self, symbol: str, ltf: str, htf: str, start: str, end: str) -> List[EntrySignal]:
        """
        Run chronological backtesting that simulates real-time processing
        """
        print(f"🔄 Starting Chronological Backtesting")
        print(f"   Symbol: {symbol}")
        print(f"   LTF: {ltf}, HTF: {htf}")
        print(f"   Period: {start} to {end}")
        print(f"   HTF Lookback: {self.htf_lookback_hours}h")
        
        # Get LTF candles for the test period
        ltf_result = self.data_service.detect_signals(
            symbol=symbol,
            signal_type="fvg_and_pivot",
            timeframe=ltf,
            start=start,
            end=end
        )
        ltf_candles = ltf_result["candles"]
        
        print(f"   📊 LTF Candles: {len(ltf_candles)}")
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(ltf_candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        signals = []
        processed_candles = 0
        
        print(f"🔍 Processing candles chronologically...")
        
        # Process each candle in chronological order
        for i, current_candle in df.iterrows():
            current_time = current_candle['timestamp']
            
            # Progress indicator
            if processed_candles % 500 == 0:
                print(f"   Processing candle {processed_candles}/{len(df)} - {current_time}")
            
            # Get HTF data that would be available at this time
            # (Only FVGs created before current_time - no look-ahead bias)
            htf_pools = self._get_htf_pools_at_time(symbol, htf, current_time)
            
            if not htf_pools.get('fvg_pools'):
                processed_candles += 1
                continue
            
            # Get historical candles up to current time for analysis
            historical_candles = df[df['timestamp'] <= current_time].to_dict('records')
            
            if len(historical_candles) < 50:  # Need enough history for EMA
                processed_candles += 1
                continue
            
            # Detect FVG events using only temporally available data
            try:
                fvg_events = self.fvg_detector.detect_events(historical_candles, htf_pools['fvg_pools'])
                
                # Process recent FVG events (within last few candles)
                for fvg_event in fvg_events:
                    event_time = pd.to_datetime(fvg_event.timestamp, utc=True)
                    
                    # Only process recent events (within last hour)
                    if (current_time - event_time).total_seconds() <= 3600:
                        signal = self._process_fvg_event(
                            fvg_event, 
                            historical_candles, 
                            current_time
                        )
                        
                        if signal and self._validate_signal(signal):
                            signals.append(signal)
                            print(f"   ✅ Signal generated at {current_time}")
                            
            except Exception as e:
                print(f"   ⚠️ Error processing candle {current_time}: {e}")
            
            processed_candles += 1
        
        print(f"✅ Chronological backtesting complete")
        print(f"   Processed {processed_candles} candles")
        print(f"   Generated {len(signals)} signals")
        
        return signals
    
    def _get_htf_pools_at_time(self, symbol: str, htf: str, current_time: datetime) -> Dict:
        """
        Get HTF pools that would be available at the given time
        This prevents data leakage by only using past information
        """
        # Calculate lookback period
        lookback_start = current_time - timedelta(hours=self.htf_lookback_hours)
        
        # Get HTF data from lookback_start to current_time
        # This simulates what would be available in real-time
        htf_result = self.data_service.detect_signals(
            symbol=symbol,
            signal_type="fvg_and_pivot",
            timeframe=htf,
            start=lookback_start.isoformat() + "Z",
            end=current_time.isoformat() + "Z"
        )
        
        # Process HTF candles to extract FVG pools
        htf_candles = htf_result["candles"]
        
        # Create FVG pools from HTF candles
        # This simulates real-time FVG detection
        fvg_pools = self._create_fvg_pools_from_candles(htf_candles, current_time)
        
        return {
            'fvg_pools': fvg_pools,
            'candles_processed': len(htf_candles)
        }
    
    def _create_fvg_pools_from_candles(self, htf_candles: List[Dict], current_time: datetime) -> List[Dict]:
        """
        Create FVG pools from HTF candles, simulating real-time detection
        Only includes FVGs that would be detected by current_time
        """
        # This is a simplified version - in a real implementation,
        # you'd run the actual FVG detection algorithm on HTF candles
        
        # For now, we'll use the existing pools but filter by time
        all_pools = self.data_service.get_liquidity_pools("BTC/USD", "4H", "all")
        fvg_pools = all_pools.get('fvg_pools', [])
        
        # Filter pools to only include those created before current_time
        available_pools = []
        for pool in fvg_pools:
            pool_time = pd.to_datetime(pool['timestamp'], utc=True)
            
            # Only include pools that were created before current evaluation time
            if pool_time <= current_time:
                # Check if within lookback window
                time_diff = (current_time - pool_time).total_seconds() / 3600
                if time_diff <= self.htf_lookback_hours:
                    available_pools.append(pool)
        
        return available_pools
    
    def _process_fvg_event(self, fvg_event, historical_candles: List[Dict], current_time: datetime) -> Optional[EntrySignal]:
        """
        Process a single FVG event to generate a signal
        """
        # Convert to DataFrame
        df = pd.DataFrame(historical_candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Find FVG event candle
        fvg_time = pd.to_datetime(fvg_event.timestamp, utc=True)
        fvg_candle_idx = None
        
        for idx, candle in df.iterrows():
            if candle['timestamp'] == fvg_time:
                fvg_candle_idx = idx
                break
        
        if fvg_candle_idx is None:
            return None
        
        # Look for swing point after FVG touch
        swing_point = self._detect_swing_point(df, fvg_candle_idx, fvg_event.direction)
        
        if not swing_point:
            return None
        
        # Look for EMA crossover after swing point
        swing_candle_idx = None
        swing_time = pd.to_datetime(swing_point['timestamp'], utc=True)
        
        for idx, candle in df.iterrows():
            if candle['timestamp'] == swing_time:
                swing_candle_idx = idx
                break
        
        if swing_candle_idx is None:
            return None
        
        # Get confirmation candles (future candles from swing point)
        confirmation_start = swing_candle_idx + 1
        confirmation_end = len(df)  # Use all available future candles
        
        if confirmation_start >= confirmation_end:
            return None
        
        confirmation_candles = df.iloc[confirmation_start:confirmation_end].to_dict('records')
        
        # Check for EMA crossover
        ema_crossover = self._find_ema_crossover(confirmation_candles, fvg_event.direction)
        
        if not ema_crossover:
            return None
        
        # Generate signal
        context = self.context_evaluator.evaluate_context(historical_candles, fvg_event)
        confidence_score = self._calculate_confidence(swing_point, ema_crossover, fvg_event)
        
        if confidence_score < self.min_confidence:
            return None
        
        # Create technical signal
        from .composable_strategy import TechnicalSignal, TrendDirection, SignalStrength
        
        tech_signal = TechnicalSignal(
            signal_type="ema_crossover",
            timestamp=ema_crossover['timestamp'],
            direction=TrendDirection.BULLISH if ema_crossover['direction'] == 'bullish' else TrendDirection.BEARISH,
            strength=SignalStrength.STRONG if confidence_score > 0.7 else SignalStrength.MEDIUM,
            confidence=confidence_score,
            values={
                'ema_fast': ema_crossover['ema_fast'],
                'ema_slow': ema_crossover['ema_slow'],
                'price': ema_crossover['price']
            }
        )
        
        entry_signal = EntrySignal(
            timestamp=swing_point['timestamp'],
            direction=fvg_event.direction,
            confidence_score=confidence_score,
            entry_price=swing_point['price'],
            technical_signals=[tech_signal],
            liquidity_event=fvg_event,
            market_context=context
        )
        
        return entry_signal
    
    def _detect_swing_point(self, df: pd.DataFrame, fvg_candle_idx: int, fvg_direction) -> Optional[Dict]:
        """
        Detect swing point formation after FVG touch
        """
        # Look at next 2-3 candles
        start_idx = fvg_candle_idx + 1
        end_idx = min(fvg_candle_idx + self.swing_lookback_candles + 1, len(df))
        
        if start_idx >= len(df):
            return None
        
        # For bearish FVG, look for swing high
        # For bullish FVG, look for swing low
        
        if fvg_direction == "bearish":
            # Find highest high in the next few candles
            highest_candle = None
            highest_price = 0
            
            for idx in range(start_idx, end_idx):
                if idx >= len(df):
                    break
                    
                candle = df.iloc[idx]
                if candle['high'] > highest_price:
                    highest_price = candle['high']
                    highest_candle = candle
            
            if highest_candle is not None:
                return {
                    'timestamp': highest_candle['timestamp'],
                    'price': highest_price,
                    'type': 'swing_high',
                    'strength': 1.0
                }
        else:  # bullish
            # Find lowest low in the next few candles
            lowest_candle = None
            lowest_price = float('inf')
            
            for idx in range(start_idx, end_idx):
                if idx >= len(df):
                    break
                    
                candle = df.iloc[idx]
                if candle['low'] < lowest_price:
                    lowest_price = candle['low']
                    lowest_candle = candle
            
            if lowest_candle is not None:
                return {
                    'timestamp': lowest_candle['timestamp'],
                    'price': lowest_price,
                    'type': 'swing_low',
                    'strength': 1.0
                }
        
        return None
    
    def _find_ema_crossover(self, confirmation_candles: List[Dict], fvg_direction: str) -> Optional[Dict]:
        """
        Find EMA crossover in confirmation candles
        """
        if len(confirmation_candles) < max(self.ema_fast_period, self.ema_slow_period):
            return None
        
        # Calculate EMAs
        df = pd.DataFrame(confirmation_candles)
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast_period).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow_period).mean()
        
        # Look for crossover
        for i in range(1, len(df)):
            prev_fast = df.iloc[i-1]['ema_fast']
            prev_slow = df.iloc[i-1]['ema_slow']
            curr_fast = df.iloc[i]['ema_fast']
            curr_slow = df.iloc[i]['ema_slow']
            
            # Check for crossover
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                # Bullish crossover
                if fvg_direction == "bearish":  # Bearish FVG expects bullish crossover
                    return {
                        'timestamp': df.iloc[i]['timestamp'],
                        'direction': 'bullish',
                        'price': df.iloc[i]['close'],
                        'ema_fast': curr_fast,
                        'ema_slow': curr_slow
                    }
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                # Bearish crossover
                if fvg_direction == "bullish":  # Bullish FVG expects bearish crossover
                    return {
                        'timestamp': df.iloc[i]['timestamp'],
                        'direction': 'bearish',
                        'price': df.iloc[i]['close'],
                        'ema_fast': curr_fast,
                        'ema_slow': curr_slow
                    }
        
        return None
    
    def _calculate_confidence(self, swing_point: Dict, ema_crossover: Dict, fvg_event) -> float:
        """
        Calculate confidence score for the signal
        """
        base_confidence = 0.6
        
        # Boost confidence based on swing strength
        if swing_point.get('strength', 0) > 0.8:
            base_confidence += 0.1
        
        # Boost confidence based on EMA separation
        ema_separation = abs(ema_crossover['ema_fast'] - ema_crossover['ema_slow'])
        if ema_separation > 100:  # Significant separation
            base_confidence += 0.1
        
        # Boost confidence based on FVG zone size
        fvg_size = fvg_event.zone_high - fvg_event.zone_low
        if fvg_size > 200:  # Large FVG zone
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def _validate_signal(self, signal: EntrySignal) -> bool:
        """
        Validate the generated signal
        """
        return (
            signal.confidence_score >= self.min_confidence and
            signal.entry_price > 0 and
            signal.technical_signals and
            len(signal.technical_signals) > 0
        )


def test_chronological_backtesting():
    """Test the chronological backtesting approach"""
    
    print("🚀 Testing Chronological Backtesting Strategy")
    print("=" * 80)
    
    # Initialize strategy
    strategy = ChronologicalBacktestingStrategy({
        "ema_fast_period": 9,
        "ema_slow_period": 20,
        "swing_lookback_candles": 3,
        "confirmation_window_hours": 12,
        "min_confidence_threshold": 0.6,
        "htf_lookback_hours": 720  # 30 days
    })
    
    # Test on the May 29 period where we know FVG touches occurred
    signals = strategy.backtest_chronological(
        symbol="BTC/USD",
        ltf="15T",
        htf="4H",
        start="2025-05-29T00:00:00Z",
        end="2025-05-30T00:00:00Z"
    )
    
    print(f"\n📊 Backtesting Results:")
    print(f"   Signals Generated: {len(signals)}")
    
    if signals:
        print(f"\n🎯 Signal Details:")
        for i, signal in enumerate(signals):
            print(f"   Signal {i+1}:")
            print(f"      • FVG Touch: {signal.liquidity_event.timestamp}")
            print(f"      • Swing Point: {signal.timestamp}")
            print(f"      • Entry Price: {signal.entry_price:.2f}")
            print(f"      • Direction: {signal.direction}")
            print(f"      • Confidence: {signal.confidence_score:.2f}")
            print(f"      • FVG Zone: {signal.liquidity_event.zone_low:.2f} - {signal.liquidity_event.zone_high:.2f}")
            
            if signal.technical_signals:
                ema_signal = signal.technical_signals[0]
                print(f"      • EMA Crossover: {ema_signal.timestamp}")
                print(f"      • EMA Fast: {ema_signal.values['ema_fast']:.2f}")
                print(f"      • EMA Slow: {ema_signal.values['ema_slow']:.2f}")
    
    print(f"\n✅ Chronological backtesting test complete!")


if __name__ == "__main__":
    test_chronological_backtesting()
