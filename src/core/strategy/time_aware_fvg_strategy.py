"""
Time-Aware FVG Strategy - Fixes Data Leakage Issues
"""

from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
from .composable_strategy import ComposableStrategy, EntrySignal
from .detectors.liquidity_pool_detectors import FVGPoolDetector, PivotPoolDetector
from .evaluators.market_context_evaluators import BasicMarketContextEvaluator
from .indicators.technical_indicators import EMACrossoverIndicator


class TimeAwareFVGStrategy(ComposableStrategy):
    """
    Strategy that properly handles temporal FVG availability
    Fixes data leakage by only using FVGs that should be known at evaluation time
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        super().__init__(self.config)
        
        # Configuration
        self.swing_lookback_candles = self.config.get("swing_lookback_candles", 3)
        self.confirmation_window_hours = self.config.get("confirmation_window_hours", 12)
        self.min_confidence = self.config.get("min_confidence_threshold", 0.6)
        self.fvg_lookback_hours = self.config.get("fvg_lookback_hours", 72)  # How far back to look for FVGs
        
        # Initialize components
        self.fvg_detector = FVGPoolDetector()
        self.pivot_detector = PivotPoolDetector()
        self.context_evaluator = BasicMarketContextEvaluator()
    
    def _get_active_fvgs_at_time(self, htf_pools: Dict, evaluation_time: datetime) -> List[Dict]:
        """
        Get FVGs that should be active/known at the evaluation time
        This prevents data leakage by only using temporally available FVGs
        """
        all_fvgs = htf_pools.get('fvg_pools', [])
        evaluation_time = pd.to_datetime(evaluation_time, utc=True)
        
        active_fvgs = []
        
        for fvg in all_fvgs:
            fvg_creation_time = pd.to_datetime(fvg['timestamp'], utc=True)
            
            # Only include FVGs that were created before current evaluation time
            if fvg_creation_time <= evaluation_time:
                
                # Check if FVG is within lookback window
                time_diff = (evaluation_time - fvg_creation_time).total_seconds() / 3600
                if time_diff <= self.fvg_lookback_hours:
                    
                    # Check if FVG should still be active (not mitigated in the past)
                    if self._is_fvg_active_at_time(fvg, evaluation_time):
                        active_fvgs.append(fvg)
        
        return active_fvgs
    
    def _is_fvg_active_at_time(self, fvg: Dict, evaluation_time: datetime) -> bool:
        """
        Check if FVG should be considered active at the evaluation time
        """
        # If no mitigation info, assume active
        if 'mitigation_time' not in fvg or fvg['mitigation_time'] is None:
            return True
        
        # If mitigation happened after evaluation time, FVG is still active
        mitigation_time = pd.to_datetime(fvg['mitigation_time'], utc=True)
        evaluation_time = pd.to_datetime(evaluation_time, utc=True)
        
        return mitigation_time > evaluation_time
    
    def generate_signals(self, candles_ltf: List[Dict], htf_pools: Dict[str, List[Dict]]) -> List[EntrySignal]:
        """
        Generate signals using time-aware FVG filtering
        """
        signals = []
        
        # Convert to DataFrame
        df = pd.DataFrame(candles_ltf)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"🔍 Processing {len(df)} candles with time-aware FVG filtering...")
        
        # Process candles in chronological order (simulate real-time)
        processed_candles = 0
        signal_count = 0
        
        for i, current_candle in df.iterrows():
            current_time = current_candle['timestamp']
            
            # Progress indicator
            if processed_candles % 500 == 0:
                print(f"   Processing candle {processed_candles}/{len(df)} - {current_time}")
            
            # Get FVGs that should be active at this time
            active_fvgs = self._get_active_fvgs_at_time(htf_pools, current_time)
            
            if not active_fvgs:
                processed_candles += 1
                continue
            
            # Get historical candles up to current time for analysis
            historical_candles = df[df['timestamp'] <= current_time].to_dict('records')
            
            if len(historical_candles) < 50:  # Need enough history for EMA
                processed_candles += 1
                continue
            
            # Detect FVG interactions using only temporally available FVGs
            try:
                fvg_events = self.fvg_detector.detect_events(historical_candles, active_fvgs)
                
                # Process recent FVG events (within last few candles)
                recent_events = [
                    event for event in fvg_events 
                    if (current_time - pd.to_datetime(event.timestamp, utc=True)).total_seconds() <= 3600  # Within 1 hour
                ]
                
                for fvg_event in recent_events:
                    signal = self._evaluate_fvg_event(fvg_event, historical_candles, current_time)
                    if signal:
                        signals.append(signal)
                        signal_count += 1
                        print(f"   ✅ Signal #{signal_count} generated at {current_time}")
                        
            except Exception as e:
                # Skip problematic candles
                pass
            
            processed_candles += 1
        
        print(f"✅ Generated {len(signals)} signals")
        return signals
    
    def _evaluate_fvg_event(self, fvg_event, historical_candles: List[Dict], current_time: datetime) -> Optional[EntrySignal]:
        """
        Evaluate a single FVG event for signal generation
        """
        df = pd.DataFrame(historical_candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Find the FVG touch candle
        fvg_time = pd.to_datetime(fvg_event.timestamp, utc=True)
        fvg_candle_idx = df[df['timestamp'] == fvg_time].index
        
        if len(fvg_candle_idx) == 0:
            return None
        
        fvg_candle_idx = fvg_candle_idx[0]
        
        # Check for swing point formation
        swing_point = self._detect_swing_point(df, fvg_candle_idx, fvg_event.direction)
        
        if not swing_point:
            return None
        
        # Look for EMA crossover within confirmation window
        confirmation_end_time = fvg_time + pd.Timedelta(hours=self.confirmation_window_hours)
        
        # Only use data available up to current evaluation time
        max_time = min(confirmation_end_time, current_time)
        
        confirmation_mask = (df['timestamp'] >= fvg_time) & (df['timestamp'] <= max_time)
        confirmation_candles = df[confirmation_mask].copy()
        
        if len(confirmation_candles) < 30:
            return None
        
        # Find EMA crossover
        ema_crossover = self._find_ema_crossover(confirmation_candles, fvg_event.direction)
        
        if not ema_crossover:
            return None
        
        # Generate signal
        context = self.context_evaluator.evaluate_context(historical_candles, fvg_event)
        
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
            timestamp=swing_point['timestamp'],
            direction=fvg_event.direction,
            confidence_score=confidence_score,
            entry_price=swing_point['price'],
            technical_signals=[tech_signal],
            liquidity_event=fvg_event,
            market_context=context
        )
        
        return entry_signal if self._validate_signal(entry_signal) else None
    
    def _detect_swing_point(self, df: pd.DataFrame, fvg_candle_idx: int, fvg_direction) -> Optional[Dict]:
        """
        Detect swing point formation after FVG touch
        """
        start_idx = fvg_candle_idx + 1
        end_idx = min(fvg_candle_idx + self.swing_lookback_candles + 1, len(df))
        
        if end_idx >= len(df):
            return None
        
        swing_candles = df.iloc[start_idx:end_idx]
        
        if len(swing_candles) < 2:
            return None
        
        # For bullish FVG, look for higher closes (bounce)
        if fvg_direction.value == 'bullish':
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


def create_time_aware_strategy(config: Optional[Dict] = None) -> TimeAwareFVGStrategy:
    """
    Create time-aware strategy with default configuration
    """
    default_config = {
        "ema_fast_period": 9,
        "ema_slow_period": 20,
        "swing_lookback_candles": 3,
        "confirmation_window_hours": 12,
        "min_confidence_threshold": 0.6,
        "fvg_lookback_hours": 72  # 3 days lookback for FVGs
    }
    
    if config:
        default_config.update(config)
    
    return TimeAwareFVGStrategy(default_config)
