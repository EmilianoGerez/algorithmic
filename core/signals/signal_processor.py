"""
Signal Processing System

Core signal generation and processing logic.
Handles multi-timeframe analysis and signal validation.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..data.models import (
    Candle,
    FVGZone,
    MarketData,
    Signal,
    SignalDirection,
    SignalType,
    StrategyConfig,
    TimeFrame,
)
from ..indicators.fvg_detector import FVGDetector
from ..indicators.technical import EMASystem


class SignalQuality(Enum):
    """Signal quality levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PREMIUM = "premium"


@dataclass
class SignalContext:
    """Context information for signal generation"""

    htf_data: Dict[TimeFrame, MarketData]
    ltf_data: MarketData
    fvg_zones: List[FVGZone]
    current_time: datetime
    strategy_config: StrategyConfig


class SignalProcessor:
    """
    Core signal processing engine.

    Handles signal generation, validation, and quality assessment
    based on market data and strategy requirements.
    """

    def __init__(self, strategy_config: StrategyConfig):
        """
        Initialize signal processor.

        Args:
            strategy_config: Strategy configuration
        """
        self.config = strategy_config
        self.fvg_detector = FVGDetector()
        self.ema_system = EMASystem()
        self.generated_signals: List[Signal] = []
        self.active_fvgs: List[FVGZone] = []

    def process_market_data(self, context: SignalContext) -> List[Signal]:
        """
        Process market data and generate signals.

        Args:
            context: Signal context with market data

        Returns:
            List of generated signals
        """
        signals = []

        # Update FVG zones
        self._update_fvg_zones(context)

        # Generate entry signals
        entry_signals = self._generate_entry_signals(context)
        signals.extend(entry_signals)

        # Generate exit signals (if needed)
        exit_signals = self._generate_exit_signals(context)
        signals.extend(exit_signals)

        # Validate and filter signals
        validated_signals = self._validate_signals(signals, context)

        # Update generated signals list
        self.generated_signals.extend(validated_signals)

        return validated_signals

    def _update_fvg_zones(self, context: SignalContext) -> None:
        """Update FVG zones from higher timeframe data"""
        new_fvgs = []

        # Process each higher timeframe
        for timeframe, market_data in context.htf_data.items():
            if not market_data.candles:
                continue

            # Detect FVGs in this timeframe
            fvg_zones = self.fvg_detector.detect_fvgs(market_data.candles)

            # Filter for recent, high-quality FVGs
            filtered_fvgs = self._filter_fvgs_by_quality(fvg_zones, context)
            new_fvgs.extend(filtered_fvgs)

        # Update active FVGs
        self.active_fvgs = new_fvgs

        # Update FVG status based on current price
        if context.ltf_data.candles:
            current_price = context.ltf_data.candles[-1].close
            for fvg in self.active_fvgs:
                self.fvg_detector.update_fvg_status(fvg, current_price)

    def _generate_entry_signals(self, context: SignalContext) -> List[Signal]:
        """Generate entry signals based on strategy logic"""
        signals = []

        if not context.ltf_data.candles or len(context.ltf_data.candles) < 50:
            return signals

        # Calculate EMAs for LTF data
        emas = self.ema_system.calculate_emas(context.ltf_data.candles)

        # Check each active FVG for entry opportunities
        for fvg_zone in self.active_fvgs:
            if fvg_zone.status != "active":
                continue

            # Check if price is interacting with FVG zone
            current_candle = context.ltf_data.candles[-1]
            if not fvg_zone.is_price_in_zone(current_candle.close):
                continue

            # Check EMA alignment
            if not self.ema_system.check_ema_alignment(emas, fvg_zone.direction.value):
                continue

            # Check consecutive closes
            if not self.ema_system.check_consecutive_closes(
                context.ltf_data.candles, emas, fvg_zone.direction.value, 2
            ):
                continue

            # Generate signal
            signal = self._create_entry_signal(fvg_zone, context, emas)
            if signal:
                signals.append(signal)

        return signals

    def _generate_exit_signals(self, context: SignalContext) -> List[Signal]:
        """Generate exit signals for active positions"""
        # This can be implemented based on specific exit rules
        # For now, return empty list as exits are handled by stop/target orders
        return []

    def _create_entry_signal(
        self, fvg_zone: FVGZone, context: SignalContext, emas: Dict[str, List]
    ) -> Optional[Signal]:
        """Create an entry signal based on FVG zone and market conditions"""
        current_candle = context.ltf_data.candles[-1]

        # Calculate entry price (current close)
        entry_price = current_candle.close

        # Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_stop_and_target(
            fvg_zone, entry_price, context.ltf_data.candles
        )

        if stop_loss is None or take_profit is None:
            return None

        # Calculate confidence and strength
        confidence = self._calculate_signal_confidence(fvg_zone, emas, context)
        strength = fvg_zone.strength

        # Apply confidence filter
        if confidence < self.config.confidence_threshold:
            return None

        # Create signal
        signal = Signal(
            timestamp=current_candle.timestamp,
            symbol=current_candle.symbol,
            direction=fvg_zone.direction,
            signal_type=SignalType.ENTRY,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            strength=strength,
            strategy_name=self.config.name,
            timeframe=context.ltf_data.timeframe,
            risk_reward_ratio=self.config.risk_reward_ratio,
            metadata={
                "fvg_zone_id": id(fvg_zone),
                "fvg_timeframe": fvg_zone.timeframe.value,
                "fvg_strength": fvg_zone.strength,
                "fvg_confidence": fvg_zone.confidence,
                "ema_alignment": True,
                "consecutive_closes": True,
                "entry_method": "fvg_retest_with_ema_confirmation",
            },
        )

        return signal

    def _calculate_stop_and_target(
        self, fvg_zone: FVGZone, entry_price: Decimal, candles: List[Candle]
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Calculate stop loss and take profit levels"""
        # Find swing levels for stop loss
        swing_levels = self._find_swing_levels(candles, lookback=20)

        if fvg_zone.direction == SignalDirection.LONG:
            # For long positions, stop below swing low
            stop_loss = swing_levels["low"] * Decimal("0.999")  # Small buffer

            # Calculate take profit based on risk/reward ratio
            risk = entry_price - stop_loss
            reward = risk * Decimal(str(self.config.risk_reward_ratio))
            take_profit = entry_price + reward

        else:  # SHORT
            # For short positions, stop above swing high
            stop_loss = swing_levels["high"] * Decimal("1.001")  # Small buffer

            # Calculate take profit based on risk/reward ratio
            risk = stop_loss - entry_price
            reward = risk * Decimal(str(self.config.risk_reward_ratio))
            take_profit = entry_price - reward

        return stop_loss, take_profit

    def _find_swing_levels(
        self, candles: List[Candle], lookback: int = 20
    ) -> Dict[str, Decimal]:
        """Find swing high and low levels"""
        if len(candles) < lookback:
            lookback = len(candles)

        recent_candles = candles[-lookback:]

        swing_high = max(c.high for c in recent_candles)
        swing_low = min(c.low for c in recent_candles)

        return {"high": swing_high, "low": swing_low}

    def _calculate_signal_confidence(
        self, fvg_zone: FVGZone, emas: Dict[str, List], context: SignalContext
    ) -> float:
        """Calculate signal confidence score"""
        confidence = fvg_zone.confidence * 0.6  # Base confidence from FVG

        # EMA trend strength bonus
        trend_strength = self.ema_system.get_trend_strength(emas)
        confidence += trend_strength * 0.2

        # Time-based bonus (trading hours)
        if self._is_optimal_trading_time(context.current_time):
            confidence += 0.1

        # Market structure bonus
        if self._is_trending_market(context.ltf_data.candles):
            confidence += 0.1

        return min(confidence, 1.0)

    def _is_optimal_trading_time(self, timestamp: datetime) -> bool:
        """Check if current time is optimal for trading"""
        # NYC trading hours logic
        hour = timestamp.hour

        # Evening session: 20:00-00:00
        if 20 <= hour <= 23:
            return True

        # Early morning: 02:00-04:00
        if 2 <= hour <= 4:
            return True

        # Day session: 08:00-13:00
        if 8 <= hour <= 13:
            return True

        return False

    def _is_trending_market(self, candles: List[Candle], period: int = 20) -> bool:
        """Check if market is trending (not consolidating)"""
        if len(candles) < period:
            return False

        recent_candles = candles[-period:]

        # Calculate price range
        high_prices = [float(c.high) for c in recent_candles]
        low_prices = [float(c.low) for c in recent_candles]

        price_range = max(high_prices) - min(low_prices)
        avg_price = sum(float(c.close) for c in recent_candles) / len(recent_candles)

        # If range is > 3% of average price, consider it trending
        return (price_range / avg_price) > 0.03

    def _filter_fvgs_by_quality(
        self, fvg_zones: List[FVGZone], context: SignalContext
    ) -> List[FVGZone]:
        """Filter FVGs based on quality criteria"""
        filtered_fvgs = []

        for fvg in fvg_zones:
            # Age filter
            age_hours = (context.current_time - fvg.timestamp).total_seconds() / 3600
            if age_hours > 168:  # 1 week
                continue

            # Quality filter
            if fvg.strength < 0.6:
                continue

            # Status filter
            if fvg.status not in ["active", "touched"]:
                continue

            filtered_fvgs.append(fvg)

        return filtered_fvgs

    def _validate_signals(
        self, signals: List[Signal], context: SignalContext
    ) -> List[Signal]:
        """Validate and filter signals"""
        validated_signals = []

        for signal in signals:
            # Basic validation
            if not self._validate_signal_basic(signal):
                continue

            # Risk management validation
            if not self._validate_risk_management(signal):
                continue

            # Timing validation
            if not self._validate_timing(signal, context):
                continue

            # Quality assessment
            signal.metadata["quality"] = self._assess_signal_quality(signal)

            validated_signals.append(signal)

        return validated_signals

    def _validate_signal_basic(self, signal: Signal) -> bool:
        """Basic signal validation"""
        if signal.entry_price <= 0:
            return False

        if signal.stop_loss is None or signal.take_profit is None:
            return False

        if signal.confidence < 0.5:
            return False

        return True

    def _validate_risk_management(self, signal: Signal) -> bool:
        """Risk management validation"""
        # Check risk/reward ratio
        actual_rr = signal.get_actual_risk_reward_ratio()
        if actual_rr is None or actual_rr < 1.5:
            return False

        # Check stop loss is reasonable
        risk_amount = signal.calculate_risk_amount()
        if risk_amount is None:
            return False

        # Risk should be reasonable percentage of entry price
        risk_percentage = float(risk_amount / signal.entry_price)
        if risk_percentage > 0.05:  # 5% max risk per trade
            return False

        return True

    def _validate_timing(self, signal: Signal, context: SignalContext) -> bool:
        """Timing validation"""
        # Check if within trading hours
        if not self._is_optimal_trading_time(signal.timestamp):
            return False

        # Check if not too close to previous signal
        if self._is_too_close_to_previous_signal(signal):
            return False

        return True

    def _is_too_close_to_previous_signal(
        self, signal: Signal, min_gap_minutes: int = 30
    ) -> bool:
        """Check if signal is too close to previous signal"""
        if not self.generated_signals:
            return False

        last_signal = self.generated_signals[-1]
        if last_signal.symbol != signal.symbol:
            return False

        time_gap = (signal.timestamp - last_signal.timestamp).total_seconds() / 60
        return time_gap < min_gap_minutes

    def _assess_signal_quality(self, signal: Signal) -> SignalQuality:
        """Assess signal quality level"""
        combined_score = (signal.confidence + signal.strength) / 2

        if combined_score >= 0.85:
            return SignalQuality.PREMIUM
        elif combined_score >= 0.75:
            return SignalQuality.HIGH
        elif combined_score >= 0.65:
            return SignalQuality.MEDIUM
        else:
            return SignalQuality.LOW

    def get_signal_statistics(self) -> Dict[str, any]:
        """Get signal generation statistics"""
        if not self.generated_signals:
            return {}

        total_signals = len(self.generated_signals)
        long_signals = sum(
            1 for s in self.generated_signals if s.direction == SignalDirection.LONG
        )
        short_signals = total_signals - long_signals

        avg_confidence = (
            sum(s.confidence for s in self.generated_signals) / total_signals
        )
        avg_strength = sum(s.strength for s in self.generated_signals) / total_signals

        quality_counts = {}
        for signal in self.generated_signals:
            quality = signal.metadata.get("quality", SignalQuality.LOW)
            quality_counts[quality.value] = quality_counts.get(quality.value, 0) + 1

        return {
            "total_signals": total_signals,
            "long_signals": long_signals,
            "short_signals": short_signals,
            "avg_confidence": avg_confidence,
            "avg_strength": avg_strength,
            "quality_distribution": quality_counts,
            "active_fvgs": len(self.active_fvgs),
        }

    def reset(self) -> None:
        """Reset the signal processor state"""
        self.generated_signals.clear()
        self.active_fvgs.clear()


class MultiTimeframeEngine:
    """
    Multi-timeframe signal generation engine.

    Coordinates analysis across multiple timeframes to generate
    high-quality trading signals.
    """

    def __init__(self, strategy_config: StrategyConfig):
        """
        Initialize multi-timeframe engine.

        Args:
            strategy_config: Strategy configuration
        """
        self.config = strategy_config
        self.signal_processor = SignalProcessor(strategy_config)
        self.timeframe_data: Dict[TimeFrame, MarketData] = {}

    def add_market_data(self, timeframe: TimeFrame, market_data: MarketData) -> None:
        """
        Add market data for a specific timeframe.

        Args:
            timeframe: Timeframe identifier
            market_data: Market data for the timeframe
        """
        self.timeframe_data[timeframe] = market_data

    def generate_signals(self) -> List[Signal]:
        """
        Generate signals using multi-timeframe analysis.

        Returns:
            List of generated signals
        """
        if not self.timeframe_data:
            return []

        # Identify LTF (lowest timeframe) for signal generation
        ltf_timeframe = min(
            self.timeframe_data.keys(),
            key=lambda x: self._timeframe_to_minutes(x),
        )
        ltf_data = self.timeframe_data[ltf_timeframe]

        # Higher timeframes for context
        htf_data = {
            tf: data for tf, data in self.timeframe_data.items() if tf != ltf_timeframe
        }

        # Create signal context
        current_time = datetime.utcnow()
        if ltf_data.candles:
            current_time = ltf_data.candles[-1].timestamp

        context = SignalContext(
            htf_data=htf_data,
            ltf_data=ltf_data,
            fvg_zones=[],
            current_time=current_time,
            strategy_config=self.config,
        )

        # Generate signals
        return self.signal_processor.process_market_data(context)

    def _timeframe_to_minutes(self, timeframe: TimeFrame) -> int:
        """Convert timeframe to minutes for comparison"""
        timeframe_minutes = {
            TimeFrame.MINUTE_1: 1,
            TimeFrame.MINUTE_5: 5,
            TimeFrame.MINUTE_15: 15,
            TimeFrame.MINUTE_30: 30,
            TimeFrame.HOUR_1: 60,
            TimeFrame.HOUR_4: 240,
            TimeFrame.DAY_1: 1440,
            TimeFrame.WEEK_1: 10080,
            TimeFrame.MONTH_1: 43200,
        }
        return timeframe_minutes.get(timeframe, 1440)

    def get_engine_status(self) -> Dict[str, any]:
        """Get engine status and statistics"""
        return {
            "timeframes": [tf.value for tf in self.timeframe_data.keys()],
            "signal_processor_stats": self.signal_processor.get_signal_statistics(),
            "last_update": datetime.utcnow().isoformat(),
        }
