"""
Time Window EMA Crossover Strategy
Optimized version that looks for EMA crossovers within time windows of pool interactions
"""

from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
from .composable_strategy import ComposableStrategy, EntrySignal
from .detectors.liquidity_pool_detectors import FVGPoolDetector, PivotPoolDetector
from .evaluators.market_context_evaluators import BasicMarketContextEvaluator
from .indicators.technical_indicators import EMACrossoverIndicator


class TimeWindowEMACrossoverStrategy(ComposableStrategy):
    """
    Strategy that looks for EMA crossovers within time windows of pool interactions
    """
    
    def __init__(self, config: Optional[Dict] = None):
        # Initialize config first
        self.config = config or {}
        
        # Initialize parent
        super().__init__(self.config)
        
        # Time window configuration
        self.time_window_hours = self.config.get("time_window_hours", 2)
        self.min_confidence = self.config.get("min_confidence_threshold", 0.6)
        
        # Initialize components
        self.fvg_detector = FVGPoolDetector()
        self.pivot_detector = PivotPoolDetector()
        self.ema_indicator = EMACrossoverIndicator(
            fast_period=self.config.get("ema_fast_period", 9),
            slow_period=self.config.get("ema_slow_period", 20)
        )
        self.context_evaluator = BasicMarketContextEvaluator()
    
    def generate_signals(self, candles_ltf: List[Dict], htf_pools: Dict[str, List[Dict]]) -> List[EntrySignal]:
        """
        Generate signals using time window approach
        """
        signals = []
        
        # Convert candles to DataFrame for easier manipulation
        df = pd.DataFrame(candles_ltf)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        print(f"🔍 Processing {len(df)} candles...")
        
        # Get limited pool events for testing
        fvg_pools = htf_pools.get('fvg_pools', [])[:5]  # Limit for testing
        pivot_pools = htf_pools.get('pivot_pools', [])[:5]
        
        # Detect pool interactions
        fvg_events = self.fvg_detector.detect_events(candles_ltf, fvg_pools)
        pivot_events = self.pivot_detector.detect_events(candles_ltf, pivot_pools)
        
        all_pool_events = fvg_events + pivot_events
        
        # Limit total events to avoid timeout
        all_pool_events = all_pool_events[:100]  # Process max 100 events
        
        print(f"📊 Found {len(all_pool_events)} pool events (limited for testing)")
        
        # Process each pool event
        for i, pool_event in enumerate(all_pool_events):
            if i % 100 == 0:
                print(f"   Processing pool event {i+1}/{len(all_pool_events)}")
            
            # Convert pool event timestamp to pandas datetime with UTC timezone
            pool_time = pd.to_datetime(pool_event.timestamp, utc=True)
            
            # Define time window around pool event
            window_start = pool_time - pd.Timedelta(hours=self.time_window_hours)
            window_end = pool_time + pd.Timedelta(hours=self.time_window_hours)
            
            # Get candles in this window - ensure timezone consistency
            df_with_tz = df.copy()
            df_with_tz['timestamp'] = pd.to_datetime(df_with_tz['timestamp'], utc=True)
            
            window_mask = (df_with_tz['timestamp'] >= window_start) & (df_with_tz['timestamp'] <= window_end)
            window_candles = df_with_tz[window_mask].to_dict('records')
            
            if len(window_candles) < 50:  # Need enough data for EMA
                continue
            
            # Look for EMA crossovers in this window
            ema_crossovers = self._find_ema_crossovers_in_window(window_candles)
            
            for crossover in ema_crossovers:
                # Evaluate market context at pool event time
                context = self.context_evaluator.evaluate_context(candles_ltf, pool_event)
                
                # Create entry signal
                entry_signal = EntrySignal(
                    timestamp=pool_event.timestamp,
                    direction=crossover['direction'],
                    confidence_score=crossover['confidence'],
                    entry_price=pool_event.price,
                    technical_signal=crossover['signal'],
                    liquidity_event=pool_event,
                    market_context=context
                )
                
                # Validate signal
                if self._validate_signal(entry_signal):
                    signals.append(entry_signal)
        
        print(f"✅ Generated {len(signals)} signals")
        return signals
    
    def _find_ema_crossovers_in_window(self, window_candles: List[Dict]) -> List[Dict]:
        """
        Find EMA crossovers in a time window
        """
        if len(window_candles) < 30:
            return []
        
        df = pd.DataFrame(window_candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=self.config.get("ema_fast_period", 9)).mean()
        df['ema_slow'] = df['close'].ewm(span=self.config.get("ema_slow_period", 20)).mean()
        
        # Detect crossovers
        df['ema_fast_above'] = df['ema_fast'] > df['ema_slow']
        df['ema_cross'] = df['ema_fast_above'] != df['ema_fast_above'].shift(1)
        
        crossovers = df[df['ema_cross'] & df['ema_cross'].notna()].copy()
        
        results = []
        for idx, row in crossovers.iterrows():
            direction = 'bullish' if row['ema_fast_above'] else 'bearish'
            
            # Calculate confidence based on EMA separation
            ema_separation = abs(row['ema_fast'] - row['ema_slow']) / row['close']
            confidence = min(0.9, max(0.5, ema_separation * 100))
            
            # Create technical signal mock
            from ..composable_strategy import TechnicalSignal
            from ...signals.signal_types import SignalDirection
            
            signal = TechnicalSignal(
                timestamp=row['timestamp'],
                direction=SignalDirection.BULLISH if direction == 'bullish' else SignalDirection.BEARISH,
                confidence=confidence,
                values={
                    'ema_fast': row['ema_fast'],
                    'ema_slow': row['ema_slow'],
                    'price': row['close']
                }
            )
            
            results.append({
                'direction': SignalDirection.BULLISH if direction == 'bullish' else SignalDirection.BEARISH,
                'confidence': confidence,
                'signal': signal,
                'timestamp': row['timestamp']
            })
        
        return results
    
    def _validate_signal(self, signal: EntrySignal) -> bool:
        """
        Validate signal
        """
        # Check minimum confidence
        if signal.confidence_score < self.min_confidence:
            return False
        
        # Check directional alignment with pool
        pool_direction = signal.liquidity_event.direction
        ema_direction = signal.direction
        
        # For FVG, we want same direction (bounce)
        if signal.liquidity_event.pool_type.value == "fvg":
            return pool_direction == ema_direction
        
        # For pivot sweeps, we want opposite direction (reversal)
        if signal.liquidity_event.pool_type.value == "pivot":
            if signal.liquidity_event.status == "swept":
                return pool_direction != ema_direction
        
        return True


def create_time_window_strategy(config: Optional[Dict] = None) -> TimeWindowEMACrossoverStrategy:
    """
    Create a time window strategy with default configuration
    """
    default_config = {
        "ema_fast_period": 9,
        "ema_slow_period": 20,
        "time_window_hours": 2,
        "min_confidence_threshold": 0.6,
        "risk_reward_ratio": 1.5
    }
    
    if config:
        default_config.update(config)
    
    return TimeWindowEMACrossoverStrategy(default_config)
