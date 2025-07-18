"""
FVG Strategy Implementation

Implementation of the proven FVG (Fair Value Gap) strategy using the new core system.
Extracts the successful logic from the legacy system with clean architecture.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from ..strategies.base_strategy import BaseStrategy, register_strategy
from ..data.models import (
    MarketData, Signal, StrategyConfig, TimeFrame, 
    SignalDirection, SignalType, Candle, FVGZone
)
from ..indicators.fvg_detector import FVGDetector, FVGFilterPresets
from ..indicators.technical import EMASystem, TechnicalIndicators
from ..signals.signal_processor import MultiTimeframeEngine, SignalContext


@register_strategy
class FVGStrategy(BaseStrategy):
    """
    Fair Value Gap Strategy Implementation
    
    Based on the proven logic from the legacy system:
    - Multi-timeframe FVG detection (HTF: 4H/1D, LTF: 15min)
    - EMA crossover confirmation (9, 20, 50 periods)
    - Swing-based risk management with 1:2 R:R
    - NYC session time filtering
    - Enhanced quality filtering
    """
    
    def __init__(self, config: StrategyConfig):
        """
        Initialize FVG Strategy.
        
        Args:
            config: Strategy configuration
        """
        super().__init__(config)
        
        # Strategy parameters with defaults
        self.htf_timeframes = self.get_parameter("htf_timeframes", [TimeFrame.HOUR_4, TimeFrame.DAY_1])
        self.ltf_timeframe = self.get_parameter("ltf_timeframe", TimeFrame.MINUTE_5)
        self.ema_periods = self.get_parameter("ema_periods", {"fast": 9, "medium": 20, "slow": 50})
        self.consecutive_closes = self.get_parameter("consecutive_closes", 2)
        self.fvg_filter_preset = self.get_parameter("fvg_filter_preset", "balanced")
        self.swing_lookback = self.get_parameter("swing_lookback", 20)
        self.nyc_hours_only = self.get_parameter("nyc_hours_only", True)
        
        # Initialize components
        self.fvg_detector = FVGDetector(self._get_fvg_filter_config())
        self.ema_system = EMASystem(
            fast_period=self.ema_periods["fast"],
            medium_period=self.ema_periods["medium"],
            slow_period=self.ema_periods["slow"]
        )
        self.multi_tf_engine = MultiTimeframeEngine(config)
        
        # State tracking
        self.active_fvgs: List[FVGZone] = []
        self.last_signal_time: Optional[datetime] = None
        self.consecutive_close_count = 0
        self.last_close_direction: Optional[str] = None
    
    def initialize(self) -> None:
        """Initialize the strategy"""
        if self.is_initialized:
            return
        
        # Validate configuration
        self._validate_configuration()
        
        # Initialize metadata
        self.metadata = {
            "strategy_type": "FVG",
            "version": "2.0",
            "timeframes": {
                "htf": [tf.value for tf in self.htf_timeframes],
                "ltf": self.ltf_timeframe.value
            },
            "ema_periods": self.ema_periods,
            "risk_reward_ratio": self.config.risk_reward_ratio,
            "filter_preset": self.fvg_filter_preset
        }
        
        self.is_initialized = True
    
    def generate_signals(self, market_data: Dict[TimeFrame, MarketData]) -> List[Signal]:
        """
        Generate trading signals based on FVG strategy logic.
        
        Args:
            market_data: Dictionary mapping timeframes to market data
            
        Returns:
            List of generated signals
        """
        if not self.is_initialized:
            self.initialize()
        
        # Validate required data
        if not self._validate_market_data(market_data):
            return []
        
        signals = []
        
        # Get LTF data
        ltf_data = market_data[self.ltf_timeframe]
        if not ltf_data.candles or len(ltf_data.candles) < 50:
            return []
        
        # Update FVG zones from HTF data
        self._update_fvg_zones(market_data)
        
        # Calculate EMAs for LTF
        emas = self.ema_system.calculate_emas(ltf_data.candles)
        if not emas or not all(len(emas[key]) > 0 for key in ["fast", "medium", "slow"]):
            return []
        
        # Check for entry signals
        for fvg_zone in self.active_fvgs:
            if fvg_zone.status != "active":
                continue
            
            signal = self._check_entry_signal(fvg_zone, ltf_data, emas)
            if signal:
                signals.append(signal)
        
        # Filter signals by quality and timing
        filtered_signals = self._filter_signals(signals, ltf_data)
        
        # Emit signals if callback is set (for backtesting)
        if self.signal_callback:
            for signal in filtered_signals:
                self.emit_signal(signal)
        
        return filtered_signals
    
    def validate_signal(self, signal: Signal) -> bool:
        """
        Validate a trading signal.
        
        Args:
            signal: Signal to validate
            
        Returns:
            True if signal is valid
        """
        # Basic validation
        if signal.entry_price <= 0:
            return False
        
        if signal.stop_loss is None or signal.take_profit is None:
            return False
        
        # Risk/reward validation
        actual_rr = signal.get_actual_risk_reward_ratio()
        if actual_rr is None or actual_rr < 1.5:
            return False
        
        # Confidence validation
        if signal.confidence < self.config.confidence_threshold:
            return False
        
        # Timing validation
        if self.nyc_hours_only and not self._is_nyc_trading_hours(signal.timestamp):
            return False
        
        return True
    
    def get_required_timeframes(self) -> List[TimeFrame]:
        """Get required timeframes for the strategy"""
        return self.htf_timeframes + [self.ltf_timeframe]
    
    def get_required_history_length(self) -> int:
        """Get minimum number of candles required"""
        return max(100, self.ema_periods["slow"] * 2)
    
    def _validate_configuration(self) -> None:
        """Validate strategy configuration"""
        if not self.htf_timeframes:
            raise ValueError("HTF timeframes cannot be empty")
        
        if self.ltf_timeframe in self.htf_timeframes:
            raise ValueError("LTF timeframe cannot be in HTF timeframes")
        
        if not all(isinstance(tf, TimeFrame) for tf in self.htf_timeframes):
            raise ValueError("All HTF timeframes must be TimeFrame enum values")
        
        if not isinstance(self.ltf_timeframe, TimeFrame):
            raise ValueError("LTF timeframe must be TimeFrame enum value")
    
    def _validate_market_data(self, market_data: Dict[TimeFrame, MarketData]) -> bool:
        """Validate market data availability"""
        required_timeframes = self.get_required_timeframes()
        
        for tf in required_timeframes:
            if tf not in market_data:
                return False
            
            if not market_data[tf].candles:
                return False
        
        return True
    
    def _get_fvg_filter_config(self):
        """Get FVG filter configuration based on preset"""
        preset_map = {
            "conservative": FVGFilterPresets.conservative,
            "balanced": FVGFilterPresets.balanced,
            "aggressive": FVGFilterPresets.aggressive,
            "scalping": FVGFilterPresets.scalping
        }
        
        preset_func = preset_map.get(self.fvg_filter_preset, FVGFilterPresets.balanced)
        return preset_func()
    
    def _update_fvg_zones(self, market_data: Dict[TimeFrame, MarketData]) -> None:
        """Update FVG zones from higher timeframe data"""
        new_fvgs = []
        
        for htf_timeframe in self.htf_timeframes:
            if htf_timeframe not in market_data:
                continue
            
            htf_data = market_data[htf_timeframe]
            if not htf_data.candles:
                continue
            
            # Detect FVGs in HTF data
            fvg_zones = self.fvg_detector.detect_fvgs(htf_data.candles)
            
            # Filter for recent, high-quality FVGs
            filtered_fvgs = self._filter_fvgs_by_age_and_quality(fvg_zones)
            new_fvgs.extend(filtered_fvgs)
        
        self.active_fvgs = new_fvgs
        
        # Update FVG status based on current LTF price
        ltf_data = market_data[self.ltf_timeframe]
        if ltf_data.candles:
            current_price = ltf_data.candles[-1].close
            for fvg in self.active_fvgs:
                self.fvg_detector.update_fvg_status(fvg, current_price)
    
    def _filter_fvgs_by_age_and_quality(self, fvg_zones: List[FVGZone]) -> List[FVGZone]:
        """Filter FVGs by age and quality"""
        filtered = []
        current_time = datetime.utcnow()
        
        for fvg in fvg_zones:
            # Age filter (max 1 week old)
            age_hours = (current_time - fvg.timestamp).total_seconds() / 3600
            if age_hours > 168:
                continue
            
            # Quality filter
            if fvg.strength < 0.6:
                continue
            
            # Status filter
            if fvg.status not in ["active", "touched"]:
                continue
            
            filtered.append(fvg)
        
        return filtered
    
    def _check_entry_signal(self, fvg_zone: FVGZone, ltf_data: MarketData, 
                           emas: Dict[str, List]) -> Optional[Signal]:
        """Check if FVG zone generates an entry signal"""
        current_candle = ltf_data.candles[-1]
        
        # Check if price is interacting with FVG zone
        if not fvg_zone.is_price_in_zone(current_candle.close):
            return None
        
        # Check EMA alignment
        if not self.ema_system.check_ema_alignment(emas, fvg_zone.direction.value):
            return None
        
        # Check consecutive closes above/below medium EMA
        if not self.ema_system.check_consecutive_closes(
            ltf_data.candles, emas, fvg_zone.direction.value, self.consecutive_closes
        ):
            return None
        
        # Check NYC trading hours
        if self.nyc_hours_only and not self._is_nyc_trading_hours(current_candle.timestamp):
            return None
        
        # Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_stop_and_target(fvg_zone, current_candle, ltf_data.candles)
        
        if stop_loss is None or take_profit is None:
            return None
        
        # Calculate confidence
        confidence = self._calculate_signal_confidence(fvg_zone, emas, ltf_data)
        
        # Create signal
        signal = Signal(
            timestamp=current_candle.timestamp,
            symbol=current_candle.symbol,
            direction=fvg_zone.direction,
            signal_type=SignalType.ENTRY,
            entry_price=current_candle.close,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            strength=fvg_zone.strength,
            strategy_name=self.config.name,
            timeframe=self.ltf_timeframe,
            risk_reward_ratio=self.config.risk_reward_ratio,
            metadata={
                "fvg_zone_id": id(fvg_zone),
                "fvg_timeframe": fvg_zone.timeframe.value,
                "fvg_strength": fvg_zone.strength,
                "fvg_confidence": fvg_zone.confidence,
                "ema_alignment": True,
                "consecutive_closes": self.consecutive_closes,
                "entry_method": "fvg_retest_with_ema_confirmation",
                "swing_lookback": self.swing_lookback,
                "filter_preset": self.fvg_filter_preset
            }
        )
        
        return signal
    
    def _calculate_stop_and_target(self, fvg_zone: FVGZone, current_candle: Candle, 
                                 candles: List[Candle]) -> tuple:
        """Calculate stop loss and take profit levels"""
        entry_price = current_candle.close
        
        # Find swing levels
        swing_levels = self._find_swing_levels(candles, self.swing_lookback)
        
        if fvg_zone.direction == SignalDirection.LONG:
            # Long position: stop below swing low
            stop_loss = swing_levels["low"] * Decimal('0.999')  # 0.1% buffer
            
            # Take profit based on R:R ratio
            risk = entry_price - stop_loss
            reward = risk * Decimal(str(self.config.risk_reward_ratio))
            take_profit = entry_price + reward
            
        else:  # SHORT
            # Short position: stop above swing high
            stop_loss = swing_levels["high"] * Decimal('1.001')  # 0.1% buffer
            
            # Take profit based on R:R ratio
            risk = stop_loss - entry_price
            reward = risk * Decimal(str(self.config.risk_reward_ratio))
            take_profit = entry_price - reward
        
        return stop_loss, take_profit
    
    def _find_swing_levels(self, candles: List[Candle], lookback: int) -> Dict[str, Decimal]:
        """Find swing high and low levels"""
        if len(candles) < lookback:
            lookback = len(candles)
        
        recent_candles = candles[-lookback:]
        
        swing_high = max(c.high for c in recent_candles)
        swing_low = min(c.low for c in recent_candles)
        
        return {
            "high": swing_high,
            "low": swing_low
        }
    
    def _calculate_signal_confidence(self, fvg_zone: FVGZone, emas: Dict[str, List], 
                                   ltf_data: MarketData) -> float:
        """Calculate signal confidence score"""
        confidence = fvg_zone.confidence * 0.6  # Base from FVG quality
        
        # EMA trend strength bonus
        trend_strength = self.ema_system.get_trend_strength(emas)
        confidence += trend_strength * 0.2
        
        # NYC hours bonus
        if self._is_nyc_trading_hours(ltf_data.candles[-1].timestamp):
            confidence += 0.1
        
        # Market trending bonus
        if self._is_market_trending(ltf_data.candles):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _is_nyc_trading_hours(self, timestamp: datetime) -> bool:
        """Check if timestamp is within NYC trading hours"""
        hour = timestamp.hour
        
        # Evening session: 20:00-00:00 (8 PM - 12 AM)
        if 20 <= hour <= 23:
            return True
        
        # Early morning: 02:00-04:00 (2 AM - 4 AM)
        if 2 <= hour <= 4:
            return True
        
        # Day session: 08:00-13:00 (8 AM - 1 PM)
        if 8 <= hour <= 13:
            return True
        
        return False
    
    def _is_market_trending(self, candles: List[Candle], period: int = 20) -> bool:
        """Check if market is trending"""
        if len(candles) < period:
            return False
        
        recent_candles = candles[-period:]
        
        # Calculate price range
        high_prices = [float(c.high) for c in recent_candles]
        low_prices = [float(c.low) for c in recent_candles]
        
        price_range = max(high_prices) - min(low_prices)
        avg_price = sum(float(c.close) for c in recent_candles) / len(recent_candles)
        
        # If range > 3% of average price, consider trending
        return (price_range / avg_price) > 0.03
    
    def _filter_signals(self, signals: List[Signal], ltf_data: MarketData) -> List[Signal]:
        """Filter signals by quality and timing"""
        filtered = []
        
        for signal in signals:
            # Validate signal
            if not self.validate_signal(signal):
                continue
            
            # Check minimum gap between signals
            if self._is_too_close_to_last_signal(signal):
                continue
            
            # Quality filter
            if signal.confidence < self.config.confidence_threshold:
                continue
            
            filtered.append(signal)
            self.last_signal_time = signal.timestamp
        
        return filtered
    
    def _is_too_close_to_last_signal(self, signal: Signal, min_gap_minutes: int = 30) -> bool:
        """Check if signal is too close to last signal"""
        if self.last_signal_time is None:
            return False
        
        time_gap = (signal.timestamp - self.last_signal_time).total_seconds() / 60
        return time_gap < min_gap_minutes
    
    def on_signal_generated(self, signal: Signal) -> None:
        """Called when a signal is generated"""
        self.last_signal_time = signal.timestamp
        
        # Log signal generation
        self.metadata["last_signal"] = {
            "timestamp": signal.timestamp.isoformat(),
            "direction": signal.direction.value,
            "confidence": signal.confidence,
            "strength": signal.strength,
            "fvg_timeframe": signal.metadata.get("fvg_timeframe")
        }
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """Get current strategy status"""
        return {
            "name": self.name,
            "is_initialized": self.is_initialized,
            "active_fvgs": len(self.active_fvgs),
            "last_signal_time": self.last_signal_time.isoformat() if self.last_signal_time else None,
            "configuration": {
                "htf_timeframes": [tf.value for tf in self.htf_timeframes],
                "ltf_timeframe": self.ltf_timeframe.value,
                "ema_periods": self.ema_periods,
                "risk_reward_ratio": self.config.risk_reward_ratio,
                "confidence_threshold": self.config.confidence_threshold,
                "filter_preset": self.fvg_filter_preset
            },
            "metadata": self.metadata
        }


def create_fvg_strategy_config(symbol: str, **kwargs) -> StrategyConfig:
    """
    Create a standard FVG strategy configuration.
    
    Args:
        symbol: Trading symbol
        **kwargs: Additional configuration parameters
        
    Returns:
        StrategyConfig for FVG strategy
    """
    default_params = {
        "htf_timeframes": [TimeFrame.HOUR_4, TimeFrame.DAY_1],
        "ltf_timeframe": TimeFrame.MINUTE_5,
        "ema_periods": {"fast": 9, "medium": 20, "slow": 50},
        "consecutive_closes": 2,
        "fvg_filter_preset": "balanced",
        "swing_lookback": 20,
        "nyc_hours_only": True
    }
    
    # Override with provided parameters
    default_params.update(kwargs)
    
    return StrategyConfig(
        name="FVGStrategy",
        symbol=symbol,
        timeframes=[TimeFrame.HOUR_4, TimeFrame.DAY_1, TimeFrame.MINUTE_5],
        risk_per_trade=0.02,
        risk_reward_ratio=2.0,
        max_positions=1,
        confidence_threshold=0.85,
        parameters=default_params
    )


def create_fvg_swing_config(symbol: str) -> StrategyConfig:
    """Create FVG strategy config optimized for swing trading"""
    return create_fvg_strategy_config(
        symbol=symbol,
        fvg_filter_preset="conservative",
        swing_lookback=30,
        confidence_threshold=0.8,
        risk_reward_ratio=3.0
    )


def create_fvg_scalp_config(symbol: str) -> StrategyConfig:
    """Create FVG strategy config optimized for scalping"""
    return create_fvg_strategy_config(
        symbol=symbol,
        htf_timeframes=[TimeFrame.MINUTE_15, TimeFrame.HOUR_1],
        ltf_timeframe=TimeFrame.MINUTE_1,
        fvg_filter_preset="scalping",
        swing_lookback=10,
        confidence_threshold=0.9,
        risk_reward_ratio=1.5
    )
