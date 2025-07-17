"""
Compositional Trading Strategy Framework

This module provides a scalable architecture for building trading strategies
using a compositional approach with liquidity pools, context evaluation, and
technical confirmations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from datetime import datetime


class LiquidityPoolType(Enum):
    FVG = "fvg"
    PIVOT = "pivot"
    SESSION_HIGH = "session_high"
    SESSION_LOW = "session_low"
    DAY_OPEN = "day_open"
    WEEK_OPEN = "week_open"


class TrendDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalStrength(Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


@dataclass
class LiquidityPoolEvent:
    """Represents an interaction with a liquidity pool"""
    pool_type: LiquidityPoolType
    timestamp: datetime
    price: float
    direction: TrendDirection  # Pool direction (bullish FVG, bearish pivot, etc.)
    zone_low: float
    zone_high: float
    status: str  # "touched", "swept", "penetrated", etc.
    pool_id: str
    timeframe: str
    metadata: Dict[str, Any] = None


@dataclass
class MarketContext:
    """Market context evaluation at the time of pool interaction"""
    timestamp: datetime
    volume_profile: Dict[str, float]  # avg_volume, relative_volume, etc.
    trend_regime: TrendDirection
    market_structure: str  # "ranging", "trending", "breakout", etc.
    volatility: float
    absorption_level: float  # 0-1 scale
    exhaustion_signals: List[str]
    metadata: Dict[str, Any] = None


@dataclass
class TechnicalSignal:
    """Technical indicator confirmation signal"""
    
    def __init__(self,
                 signal_type: str,
                 timestamp: datetime,
                 direction: TrendDirection,
                 strength: SignalStrength,
                 confidence: float,
                 values: Dict[str, float],
                 metadata: Dict[str, Any] = None):
        
        self.signal_type = signal_type
        self.timestamp = timestamp
        self.direction = direction
        self.strength = strength
        self.confidence = confidence
        self.values = values
        self.metadata = metadata or {}
    
    signal_type: str  # "ema_crossover", "rsi_divergence", etc.
    timestamp: datetime
    direction: TrendDirection
    strength: SignalStrength
    confidence: float  # 0-1 scale
    values: Dict[str, float]  # indicator values
    metadata: Dict[str, Any] = None


@dataclass
class EntrySignal:
    """Final entry signal combining all components"""
    
    def __init__(self, 
                 timestamp: datetime,
                 symbol: str = "",
                 direction: TrendDirection = None,
                 entry_price: float = 0.0,
                 liquidity_event: LiquidityPoolEvent = None,
                 market_context: MarketContext = None,
                 technical_signals: List[TechnicalSignal] = None,
                 stop_loss: float = 0.0,
                 take_profit: float = 0.0,
                 risk_reward_ratio: float = 0.0,
                 confidence_score: float = 0.0,
                 strength_score: float = 0.0,
                 strategy_name: str = "",
                 timeframe: str = "",
                 metadata: Dict[str, Any] = None):
        
        self.timestamp = timestamp
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.liquidity_event = liquidity_event
        self.market_context = market_context
        self.technical_signals = technical_signals or []
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.risk_reward_ratio = risk_reward_ratio
        self.confidence_score = confidence_score
        self.strength_score = strength_score
        self.strategy_name = strategy_name
        self.timeframe = timeframe
        self.metadata = metadata or {}
    
    timestamp: datetime
    symbol: str
    direction: TrendDirection
    entry_price: float
    
    # Components
    liquidity_event: LiquidityPoolEvent
    market_context: MarketContext
    technical_signals: List[TechnicalSignal]
    
    # Risk management
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    
    # Scoring
    confidence_score: float
    strength_score: float
    
    # Metadata
    strategy_name: str
    timeframe: str
    metadata: Dict[str, Any] = None


class LiquidityPoolDetector(ABC):
    """Abstract base class for liquidity pool event detection"""
    
    @abstractmethod
    def detect_events(self, candles: List[Dict], pools: List[Dict]) -> List[LiquidityPoolEvent]:
        """Detect interactions between price and liquidity pools"""
        pass


class ContextEvaluator(ABC):
    """Abstract base class for market context evaluation"""
    
    @abstractmethod
    def evaluate_context(self, candles: List[Dict], event: LiquidityPoolEvent) -> MarketContext:
        """Evaluate market context at the time of liquidity pool interaction"""
        pass


class TechnicalIndicator(ABC):
    """Abstract base class for technical indicators"""
    
    @abstractmethod
    def generate_signal(self, candles: List[Dict], context: MarketContext) -> Optional[TechnicalSignal]:
        """Generate technical signal based on candles and context"""
        pass


class ComposableStrategy:
    """
    Main strategy engine that combines liquidity pool events,
    context evaluation, and technical confirmations
    """
    
    def __init__(self, name: str):
        self.name = name
        self.pool_detectors: List[LiquidityPoolDetector] = []
        self.context_evaluators: List[ContextEvaluator] = []
        self.technical_indicators: List[TechnicalIndicator] = []
        self.enabled = True
    
    def add_pool_detector(self, detector: LiquidityPoolDetector):
        """Add a liquidity pool detector"""
        self.pool_detectors.append(detector)
    
    def add_context_evaluator(self, evaluator: ContextEvaluator):
        """Add a context evaluator"""
        self.context_evaluators.append(evaluator)
    
    def add_technical_indicator(self, indicator: TechnicalIndicator):
        """Add a technical indicator"""
        self.technical_indicators.append(indicator)
    
    def generate_signals(self, candles_ltf: List[Dict], htf_pools: Dict[str, List[Dict]]) -> List[EntrySignal]:
        """
        Generate entry signals by combining all components
        
        Args:
            candles_ltf: Low timeframe candles for entry decisions
            htf_pools: High timeframe liquidity pools
        
        Returns:
            List of entry signals
        """
        entry_signals = []
        
        # Step 1: Detect liquidity pool events
        pool_events = []
        for detector in self.pool_detectors:
            # Combine all pool types for detection
            all_pools = []
            for pool_type, pools in htf_pools.items():
                all_pools.extend(pools)
            
            events = detector.detect_events(candles_ltf, all_pools)
            pool_events.extend(events)
        
        # Step 2: For each pool event, evaluate context and technical signals
        for event in pool_events:
            try:
                # Evaluate market context
                market_context = None
                for evaluator in self.context_evaluators:
                    context = evaluator.evaluate_context(candles_ltf, event)
                    if context:
                        market_context = context
                        break
                
                if not market_context:
                    continue
                
                # Generate technical signals
                technical_signals = []
                for indicator in self.technical_indicators:
                    signal = indicator.generate_signal(candles_ltf, market_context)
                    if signal:
                        technical_signals.append(signal)
                
                # Step 3: Combine signals into entry signal
                if technical_signals:
                    entry_signal = self._create_entry_signal(
                        event, market_context, technical_signals, candles_ltf
                    )
                    
                    if entry_signal:
                        entry_signals.append(entry_signal)
                        
            except Exception as e:
                print(f"Error processing event {event.pool_id}: {e}")
                continue
        
        return entry_signals
    
    def _create_entry_signal(self, event: LiquidityPoolEvent, context: MarketContext, 
                           technical_signals: List[TechnicalSignal], candles: List[Dict]) -> Optional[EntrySignal]:
        """Create final entry signal from components"""
        
        # Get current price (last candle)
        current_price = candles[-1]['close']
        
        # Determine direction based on pool and technical signals
        # For now, use technical signal direction
        direction = technical_signals[0].direction
        
        # Calculate confidence score (average of technical signals)
        confidence = sum(signal.confidence for signal in technical_signals) / len(technical_signals)
        
        # Calculate strength score based on technical signals
        strength_scores = {"weak": 0.3, "medium": 0.6, "strong": 0.9}
        strength = sum(strength_scores.get(signal.strength.value, 0.5) for signal in technical_signals) / len(technical_signals)
        
        # Basic risk management (can be enhanced)
        if direction == TrendDirection.BULLISH:
            stop_loss = min(event.zone_low, current_price * 0.98)  # 2% or zone low
            take_profit = current_price * 1.06  # 3:1 RR
        else:
            stop_loss = max(event.zone_high, current_price * 1.02)  # 2% or zone high
            take_profit = current_price * 0.94  # 3:1 RR
        
        risk_reward = abs(take_profit - current_price) / abs(stop_loss - current_price)
        
        # Only generate signal if confidence is high enough
        if confidence >= 0.6:
            return EntrySignal(
                timestamp=datetime.now(),
                symbol="BTC/USD",  # TODO: Make dynamic
                direction=direction,
                entry_price=current_price,
                liquidity_event=event,
                market_context=context,
                technical_signals=technical_signals,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=risk_reward,
                confidence_score=confidence,
                strength_score=strength,
                strategy_name=self.name,
                timeframe="15T",  # TODO: Make dynamic
                metadata={"created_by": "ComposableStrategy"}
            )
        
        return None
