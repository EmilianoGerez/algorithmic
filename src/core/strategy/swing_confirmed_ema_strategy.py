"""
Correct EMA Crossover Strategy Implementation
Based on proper understanding of timing sequence
"""

from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
from .composable_strategy import ComposableStrategy, EntrySignal
from .detectors.liquidity_pool_detectors import FVGPoolDetector, PivotPoolDetector
from .evaluators.market_context_evaluators import BasicMarketContextEvaluator
from .indicators.technical_indicators import EMACrossoverIndicator


class SwingConfirmedEMACrossoverStrategy(ComposableStrategy):
    """
    Strategy that:
    1. Detects FVG touch
    2. Waits for swing point formation (2-3 candles after)
    3. Looks for EMA crossover within 4H window
    4. Generates signal when all conditions align
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        super().__init__(self.config)
        
        # Configuration
        self.swing_lookback_candles = self.config.get("swing_lookback_candles", 3)
        self.confirmation_window_hours = self.config.get("confirmation_window_hours", 12)  # Extended window
        self.min_confidence = self.config.get("min_confidence_threshold", 0.6)
        
        # Initialize components
        self.fvg_detector = FVGPoolDetector()
        self.pivot_detector = PivotPoolDetector()
        self.context_evaluator = BasicMarketContextEvaluator()
    
    def generate_signals(self, candles_ltf: List[Dict], htf_pools: Dict[str, List[Dict]]) -> List[EntrySignal]:
        """
        Generate signals with correct timing sequence
        """
        signals = []
        
        # Convert to DataFrame
        df = pd.DataFrame(candles_ltf)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"🔍 Processing {len(df)} candles...")
        
        # Get limited pool events for testing
        fvg_pools = htf_pools.get('fvg_pools', [])[:5]
        pivot_pools = htf_pools.get('pivot_pools', [])[:5]
        
        # Detect FVG interactions
        fvg_events = self.fvg_detector.detect_events(candles_ltf, fvg_pools)
        
        # Limit events for testing
        fvg_events = fvg_events[:20]
        
        print(f"📊 Found {len(fvg_events)} FVG events")
        
        # Process each FVG touch
        for i, fvg_event in enumerate(fvg_events):
            if i % 5 == 0:
                print(f"   Processing FVG event {i+1}/{len(fvg_events)}")
            
            # Step 1: Find the candle where FVG was touched
            fvg_time = pd.to_datetime(fvg_event.timestamp, utc=True)
            
            # Find the candle index
            candle_idx = df[df['timestamp'] == fvg_time].index
            if len(candle_idx) == 0:
                continue
            
            candle_idx = candle_idx[0]
            
            # Step 2: Wait for swing point formation (2-3 candles after)
            swing_start_idx = candle_idx + 1
            swing_end_idx = min(candle_idx + self.swing_lookback_candles + 1, len(df))
            
            if swing_end_idx >= len(df):
                continue
            
            # Check for swing point formation
            swing_point = self._detect_swing_point(df, candle_idx, fvg_event.direction)
            
            if not swing_point:
                continue
            
            # Step 3: Look for EMA crossover within confirmation window
            confirmation_end_time = fvg_time + pd.Timedelta(hours=self.confirmation_window_hours)
            
            # Get candles in confirmation window
            confirmation_mask = (df['timestamp'] >= fvg_time) & (df['timestamp'] <= confirmation_end_time)
            confirmation_candles = df[confirmation_mask].copy()
            
            if len(confirmation_candles) < 30:  # Need enough data for EMA
                continue
            
            # Step 4: Check for EMA crossover
            ema_crossover = self._find_ema_crossover(confirmation_candles, fvg_event.direction)
            
            if ema_crossover:
                # Generate signal
                context = self.context_evaluator.evaluate_context(candles_ltf, fvg_event)
                
                # Create technical signal object
                from .composable_strategy import TechnicalSignal, TrendDirection, SignalStrength
                
                confidence_score = self._calculate_confidence(swing_point, ema_crossover, fvg_event)
                
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
                    timestamp=swing_point['timestamp'],  # Use swing point time
                    direction=fvg_event.direction,
                    confidence_score=confidence_score,
                    entry_price=swing_point['price'],
                    technical_signals=[tech_signal],  # Use plural
                    liquidity_event=fvg_event,
                    market_context=context
                )
                
                if self._validate_signal(entry_signal):
                    signals.append(entry_signal)
                    print(f"   ✅ Signal generated at {swing_point['timestamp']}")
        
        print(f"✅ Generated {len(signals)} signals")
        return signals
    
    def _detect_swing_point(self, df: pd.DataFrame, fvg_candle_idx: int, fvg_direction) -> Optional[Dict]:
        """
        Detect swing point formation after FVG touch
        """
        # Look at next 2-3 candles
        start_idx = fvg_candle_idx + 1
        end_idx = min(fvg_candle_idx + self.swing_lookback_candles + 1, len(df))
        
        if end_idx >= len(df):
            return None
        
        # Get candles after FVG touch
        swing_candles = df.iloc[start_idx:end_idx]
        
        if len(swing_candles) < 2:
            return None
        
        # For bullish FVG, look for higher closes (bounce)
        if fvg_direction.value == 'bullish':
            # Check if we have 2+ candles with higher closes
            closes = swing_candles['close'].values
            if len(closes) >= 2 and closes[-1] > closes[0]:
                return {
                    'timestamp': swing_candles.iloc[-1]['timestamp'],
                    'price': swing_candles.iloc[-1]['close'],
                    'type': 'bullish_swing',
                    'strength': (closes[-1] - closes[0]) / closes[0]
                }
        
        # For bearish FVG, look for lower closes (rejection)
        elif fvg_direction.value == 'bearish':
            closes = swing_candles['close'].values
            if len(closes) >= 2 and closes[-1] < closes[0]:
                return {
                    'timestamp': swing_candles.iloc[-1]['timestamp'],
                    'price': swing_candles.iloc[-1]['close'],
                    'type': 'bearish_swing',
                    'strength': (closes[0] - closes[-1]) / closes[0]
                }
        
        return None
    
    def _find_ema_crossover(self, confirmation_candles: pd.DataFrame, expected_direction) -> Optional[Dict]:
        """
        Find EMA crossover in confirmation window
        """
        if len(confirmation_candles) < 30:
            return None
        
        # Calculate EMAs
        fast_period = self.config.get("ema_fast_period", 9)
        slow_period = self.config.get("ema_slow_period", 20)
        
        confirmation_candles = confirmation_candles.copy()
        confirmation_candles['ema_fast'] = confirmation_candles['close'].ewm(span=fast_period).mean()
        confirmation_candles['ema_slow'] = confirmation_candles['close'].ewm(span=slow_period).mean()
        
        # Detect crossovers
        confirmation_candles['ema_fast_above'] = confirmation_candles['ema_fast'] > confirmation_candles['ema_slow']
        confirmation_candles['ema_cross'] = confirmation_candles['ema_fast_above'] != confirmation_candles['ema_fast_above'].shift(1)
        
        crossovers = confirmation_candles[confirmation_candles['ema_cross'] & confirmation_candles['ema_cross'].notna()]
        
        # Look for crossover in expected direction
        for idx, row in crossovers.iterrows():
            crossover_direction = 'bullish' if row['ema_fast_above'] else 'bearish'
            
            if crossover_direction == expected_direction.value:
                return {
                    'timestamp': row['timestamp'],
                    'direction': crossover_direction,
                    'ema_fast': row['ema_fast'],
                    'ema_slow': row['ema_slow'],
                    'price': row['close']
                }
        
        return None
    
    def _calculate_confidence(self, swing_point: Dict, ema_crossover: Dict, fvg_event) -> float:
        """
        Calculate confidence based on swing strength and EMA separation
        """
        # Base confidence
        confidence = 0.5
        
        # Swing strength contribution
        swing_strength = swing_point.get('strength', 0)
        confidence += min(0.3, swing_strength * 10)
        
        # EMA separation contribution
        ema_separation = abs(ema_crossover['ema_fast'] - ema_crossover['ema_slow']) / ema_crossover['price']
        confidence += min(0.2, ema_separation * 100)
        
        return min(0.95, confidence)
    
    def _validate_signal(self, signal: EntrySignal) -> bool:
        """
        Validate signal
        """
        return signal.confidence_score >= self.min_confidence


def create_swing_confirmed_strategy(config: Optional[Dict] = None) -> SwingConfirmedEMACrossoverStrategy:
    """
    Create swing confirmed strategy with default configuration
    """
    default_config = {
        "ema_fast_period": 9,
        "ema_slow_period": 20,
        "swing_lookback_candles": 3,
        "confirmation_window_hours": 12,  # Extended window
        "min_confidence_threshold": 0.6
    }
    
    if config:
        default_config.update(config)
    
    return SwingConfirmedEMACrossoverStrategy(default_config)
