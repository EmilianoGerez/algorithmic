"""
EMA Crossover in Liquidity Pool Strategy

This implements your specific strategy:
1. Detect liquidity pool interactions (FVG touch, pivot sweep)
2. Evaluate market context
3. Confirm with EMA crossover signals
4. Generate entry signals
"""

from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
from .composable_strategy import ComposableStrategy, EntrySignal
from .detectors.liquidity_pool_detectors import FVGPoolDetector, PivotPoolDetector
from .evaluators.market_context_evaluators import BasicMarketContextEvaluator
from .indicators.technical_indicators import EMACrossoverIndicator, RSIDivergenceIndicator


class EMACrossoverInPoolStrategy(ComposableStrategy):
    """
    EMA Crossover in Liquidity Pool Strategy
    
    Strategy Logic:
    1. Wait for price to reach a liquidity pool (FVG touch/sweep or pivot interaction)
    2. Evaluate market context (volume, trend, structure)
    3. Look for EMA crossover confirmation
    4. Generate entry signal if all conditions are met
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the EMA crossover strategy
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__("EMA Crossover in Liquidity Pool")
        
        # Default configuration
        self.config = {
            "ema_fast_period": 9,
            "ema_slow_period": 20,
            "ema_lookback_candles": 5,
            "ema_min_separation": 0.001,
            "fvg_touch_threshold": 0.001,
            "pivot_sweep_threshold": 0.0005,
            "volume_lookback": 20,
            "volatility_lookback": 20,
            "enable_rsi_divergence": True,
            "min_confidence_threshold": 0.6,
            "risk_reward_ratio": 2.0
        }
        
        # Update with provided config
        if config:
            self.config.update(config)
        
        # Initialize components
        self._setup_components()
    
    def _setup_components(self):
        """Setup strategy components"""
        
        # Liquidity pool detectors
        fvg_detector = FVGPoolDetector(
            touch_threshold=self.config["fvg_touch_threshold"]
        )
        pivot_detector = PivotPoolDetector(
            sweep_threshold=self.config["pivot_sweep_threshold"]
        )
        
        self.add_pool_detector(fvg_detector)
        self.add_pool_detector(pivot_detector)
        
        # Market context evaluator
        context_evaluator = BasicMarketContextEvaluator(
            volume_lookback=self.config["volume_lookback"],
            volatility_lookback=self.config["volatility_lookback"]
        )
        self.add_context_evaluator(context_evaluator)
        
        # Technical indicators
        ema_indicator = EMACrossoverIndicator(
            fast_period=self.config["ema_fast_period"],
            slow_period=self.config["ema_slow_period"],
            lookback_candles=self.config["ema_lookback_candles"],
            min_separation=self.config["ema_min_separation"]
        )
        self.add_technical_indicator(ema_indicator)
        
        # Optional RSI divergence
        if self.config["enable_rsi_divergence"]:
            rsi_indicator = RSIDivergenceIndicator()
            self.add_technical_indicator(rsi_indicator)
    
    def generate_signals(self, candles_ltf: List[Dict], htf_pools: Dict[str, List[Dict]]) -> List[EntrySignal]:
        """
        Generate entry signals with strategy-specific logic
        
        Args:
            candles_ltf: Low timeframe candles for entry decisions
            htf_pools: High timeframe liquidity pools
        
        Returns:
            List of entry signals
        """
        
        # Use parent class logic but add strategy-specific filtering
        signals = super().generate_signals(candles_ltf, htf_pools)
        
        # Apply strategy-specific filters
        filtered_signals = []
        
        for signal in signals:
            if self._validate_signal(signal):
                # Enhance signal with strategy-specific logic
                enhanced_signal = self._enhance_signal(signal)
                filtered_signals.append(enhanced_signal)
        
        return filtered_signals
    
    def _validate_signal(self, signal: EntrySignal) -> bool:
        """
        Validate signal against strategy-specific criteria
        
        Args:
            signal: Entry signal to validate
        
        Returns:
            True if signal is valid
        """
        
        # Check minimum confidence threshold
        if signal.confidence_score < self.config["min_confidence_threshold"]:
            return False
        
        # Check risk/reward ratio
        if signal.risk_reward_ratio < self.config["risk_reward_ratio"]:
            return False
        
        # Strategy-specific validation
        return self._validate_ema_pool_alignment(signal) and self._validate_timing_alignment(signal)
    
    def _validate_timing_alignment(self, signal: EntrySignal) -> bool:
        """
        Validate that EMA crossover happens within reasonable time of pool interaction
        """
        if not signal.technical_signal or not signal.liquidity_event:
            return False
        
        # Convert timestamps to datetime for comparison
        ema_time = pd.to_datetime(signal.technical_signal.timestamp)
        pool_time = pd.to_datetime(signal.liquidity_event.timestamp)
        
        # Allow EMA crossover within 2 hours of pool event (8 candles)
        time_diff = abs((ema_time - pool_time).total_seconds())
        max_time_diff = 2 * 60 * 60  # 2 hours
        
        return time_diff <= max_time_diff
    
    def _validate_ema_pool_alignment(self, signal: EntrySignal) -> bool:
        """
        Validate that EMA crossover aligns with liquidity pool direction
        
        Args:
            signal: Entry signal to validate
        
        Returns:
            True if alignment is valid
        """
        
        pool_direction = signal.liquidity_event.direction
        ema_direction = signal.direction
        
        # For bullish FVG, we want bullish EMA crossover (price bounces up)
        # For bearish FVG, we want bearish EMA crossover (price bounces down)
        # For pivot sweeps, we want opposite direction (contrarian)
        
        if signal.liquidity_event.pool_type.value == "fvg":
            # FVG: Look for bounce in same direction as FVG
            return pool_direction == ema_direction
        
        elif signal.liquidity_event.pool_type.value == "pivot":
            # Pivot: Look for reversal (opposite direction)
            if signal.liquidity_event.status == "swept":
                return pool_direction != ema_direction
            else:
                return pool_direction == ema_direction
        
        return True
    
    def _enhance_signal(self, signal: EntrySignal) -> EntrySignal:
        """
        Enhance signal with strategy-specific information
        
        Args:
            signal: Original entry signal
        
        Returns:
            Enhanced entry signal
        """
        
        # Add strategy-specific metadata
        if signal.metadata is None:
            signal.metadata = {}
        
        signal.metadata.update({
            "strategy_version": "1.0",
            "pool_type": signal.liquidity_event.pool_type.value,
            "pool_status": signal.liquidity_event.status,
            "ema_config": {
                "fast_period": self.config["ema_fast_period"],
                "slow_period": self.config["ema_slow_period"]
            },
            "market_regime": signal.market_context.trend_regime.value,
            "volume_analysis": signal.market_context.volume_profile,
            "exhaustion_signals": signal.market_context.exhaustion_signals
        })
        
        # Enhance confidence based on additional factors
        signal.confidence_score = self._calculate_enhanced_confidence(signal)
        
        return signal
    
    def _calculate_enhanced_confidence(self, signal: EntrySignal) -> float:
        """
        Calculate enhanced confidence score based on multiple factors
        
        Args:
            signal: Entry signal
        
        Returns:
            Enhanced confidence score (0-1)
        """
        
        base_confidence = signal.confidence_score
        
        # Volume confirmation bonus
        volume_bonus = 0.0
        if signal.market_context.volume_profile.get("relative_volume", 1.0) > 1.5:
            volume_bonus = 0.1
        
        # Market structure bonus
        structure_bonus = 0.0
        if signal.market_context.market_structure in ["trending", "breakout"]:
            structure_bonus = 0.05
        
        # Exhaustion penalty
        exhaustion_penalty = 0.0
        if len(signal.market_context.exhaustion_signals) > 1:
            exhaustion_penalty = 0.05
        
        # Pool quality bonus
        pool_bonus = 0.0
        if signal.liquidity_event.pool_type.value == "fvg":
            zone_size = signal.liquidity_event.zone_high - signal.liquidity_event.zone_low
            if zone_size > signal.entry_price * 0.005:  # > 0.5% of price
                pool_bonus = 0.05
        
        # Calculate final confidence
        enhanced_confidence = base_confidence + volume_bonus + structure_bonus + pool_bonus - exhaustion_penalty
        
        # Clamp between 0 and 1
        return max(0.0, min(1.0, enhanced_confidence))
    
    def get_strategy_summary(self) -> Dict:
        """Get strategy configuration summary"""
        
        return {
            "name": self.name,
            "config": self.config,
            "components": {
                "pool_detectors": len(self.pool_detectors),
                "context_evaluators": len(self.context_evaluators),
                "technical_indicators": len(self.technical_indicators)
            },
            "description": "EMA crossover strategy triggered by liquidity pool interactions",
            "timeframes": {
                "entry": "15T",
                "context": "4H"
            }
        }


def create_default_strategy() -> EMACrossoverInPoolStrategy:
    """Create default EMA crossover strategy"""
    
    return EMACrossoverInPoolStrategy()


def create_scalping_strategy() -> EMACrossoverInPoolStrategy:
    """Create scalping version with faster settings"""
    
    config = {
        "ema_fast_period": 5,
        "ema_slow_period": 13,
        "ema_lookback_candles": 3,
        "ema_min_separation": 0.0005,
        "fvg_touch_threshold": 0.0005,
        "pivot_sweep_threshold": 0.0003,
        "volume_lookback": 10,
        "volatility_lookback": 10,
        "enable_rsi_divergence": False,
        "min_confidence_threshold": 0.5,
        "risk_reward_ratio": 1.5
    }
    
    return EMACrossoverInPoolStrategy(config)


def create_swing_strategy() -> EMACrossoverInPoolStrategy:
    """Create swing trading version with slower settings"""
    
    config = {
        "ema_fast_period": 21,
        "ema_slow_period": 50,
        "ema_lookback_candles": 10,
        "ema_min_separation": 0.002,
        "fvg_touch_threshold": 0.002,
        "pivot_sweep_threshold": 0.001,
        "volume_lookback": 50,
        "volatility_lookback": 50,
        "enable_rsi_divergence": True,
        "min_confidence_threshold": 0.7,
        "risk_reward_ratio": 3.0
    }
    
    return EMACrossoverInPoolStrategy(config)
