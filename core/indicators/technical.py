"""
Technical Indicators Library

Centralized collection of technical indicators for the trading system.
Clean, efficient implementations with standardized interfaces.
."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..data.models import Candle


@dataclass
class IndicatorResult:
    """Result of an indicator calculation."""

    value: float
    timestamp: Optional[object] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TechnicalIndicators:
    """
    Collection of technical indicators with clean, standardized interfaces.

    All indicators follow the same pattern:
    - Accept list[Candle] as input
    - Return list[IndicatorResult] or single values
    - Handle edge cases gracefully
    - Provide configurable parameters
    ."""

    @staticmethod
    def ema(candles: list[Candle], period: int) -> list[IndicatorResult]:
        """
        Exponential Moving Average

        Args:
            candles: List of candles
            period: EMA period

        Returns:
            List of EMA values
        ."""
        if len(candles) < period:
            return []

        closes = [float(c.close) for c in candles]
        alpha = 2.0 / (period + 1)

        results = []
        ema_value = closes[0]  # Start with first close

        for i, candle in enumerate(candles):
            if i == 0:
                ema_value = closes[i]
            else:
                ema_value = alpha * closes[i] + (1 - alpha) * ema_value

            results.append(
                IndicatorResult(
                    value=ema_value,
                    timestamp=candle.timestamp,
                    metadata={"period": period},
                )
            )

        return results

    @staticmethod
    def sma(candles: list[Candle], period: int) -> list[IndicatorResult]:
        """
        Simple Moving Average

        Args:
            candles: List of candles
            period: SMA period

        Returns:
            List of SMA values
        ."""
        if len(candles) < period:
            return []

        closes = [float(c.close) for c in candles]
        results = []

        for i in range(period - 1, len(candles)):
            sma_value = sum(closes[i - period + 1 : i + 1]) / period
            results.append(
                IndicatorResult(
                    value=sma_value,
                    timestamp=candles[i].timestamp,
                    metadata={"period": period},
                )
            )

        return results

    @staticmethod
    def rsi(candles: list[Candle], period: int = 14) -> list[IndicatorResult]:
        """
        Relative Strength Index

        Args:
            candles: List of candles
            period: RSI period (default 14)

        Returns:
            List of RSI values
        ."""
        if len(candles) < period + 1:
            return []

        closes = [float(c.close) for c in candles]
        gains = []
        losses = []

        # Calculate gains and losses
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        results = []

        # Calculate initial averages
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            # Smooth the averages
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            # Calculate RSI
            if avg_loss == 0:
                rsi_value = 100
            else:
                rs = avg_gain / avg_loss
                rsi_value = 100 - (100 / (1 + rs))

            results.append(
                IndicatorResult(
                    value=rsi_value,
                    timestamp=candles[i + 1].timestamp,
                    metadata={"period": period},
                )
            )

        return results

    @staticmethod
    def atr(candles: list[Candle], period: int = 14) -> list[IndicatorResult]:
        """
        Average True Range

        Args:
            candles: List of candles
            period: ATR period (default 14)

        Returns:
            List of ATR values
        ."""
        if len(candles) < period + 1:
            return []

        true_ranges = []

        for i in range(1, len(candles)):
            current = candles[i]
            previous = candles[i - 1]

            tr = max(
                float(current.high - current.low),
                abs(float(current.high - previous.close)),
                abs(float(current.low - previous.close)),
            )
            true_ranges.append(tr)

        results = []

        # Calculate initial ATR
        atr_value = sum(true_ranges[:period]) / period

        for i in range(period, len(true_ranges)):
            # Smooth the ATR
            atr_value = (atr_value * (period - 1) + true_ranges[i]) / period

            results.append(
                IndicatorResult(
                    value=atr_value,
                    timestamp=candles[i + 1].timestamp,
                    metadata={"period": period},
                )
            )

        return results

    @staticmethod
    def macd(
        candles: list[Candle],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Dict[str, list[IndicatorResult]]:
        """
        Moving Average Convergence Divergence

        Args:
            candles: List of candles
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line EMA period (default 9)

        Returns:
            Dictionary with 'macd', 'signal', and 'histogram' keys
        ."""
        if len(candles) < slow_period:
            return {"macd": [], "signal": [], "histogram": []}

        # Calculate EMAs
        fast_ema = TechnicalIndicators.ema(candles, fast_period)
        slow_ema = TechnicalIndicators.ema(candles, slow_period)

        # Calculate MACD line
        macd_line = []
        start_idx = slow_period - 1

        for i in range(start_idx, len(fast_ema)):
            macd_value = fast_ema[i].value - slow_ema[i - start_idx].value
            macd_line.append(
                IndicatorResult(
                    value=macd_value,
                    timestamp=candles[i].timestamp,
                    metadata={
                        "fast_period": fast_period,
                        "slow_period": slow_period,
                    },
                )
            )

        # Calculate signal line (EMA of MACD)
        if len(macd_line) < signal_period:
            return {"macd": macd_line, "signal": [], "histogram": []}

        macd_values = [result.value for result in macd_line]
        alpha = 2.0 / (signal_period + 1)
        signal_line = []
        signal_value = macd_values[0]

        for i, macd_result in enumerate(macd_line):
            if i == 0:
                signal_value = macd_values[i]
            else:
                signal_value = alpha * macd_values[i] + (1 - alpha) * signal_value

            signal_line.append(
                IndicatorResult(
                    value=signal_value,
                    timestamp=macd_result.timestamp,
                    metadata={"signal_period": signal_period},
                )
            )

        # Calculate histogram
        histogram = []
        for i in range(len(signal_line)):
            hist_value = macd_line[i].value - signal_line[i].value
            histogram.append(
                IndicatorResult(
                    value=hist_value,
                    timestamp=macd_line[i].timestamp,
                    metadata={"type": "histogram"},
                )
            )

        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
        }

    @staticmethod
    def bollinger_bands(
        candles: list[Candle], period: int = 20, std_dev: float = 2.0
    ) -> Dict[str, list[IndicatorResult]]:
        """
        Bollinger Bands

        Args:
            candles: List of candles
            period: Moving average period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)

        Returns:
            Dictionary with 'upper', 'middle', and 'lower' keys
        ."""
        if len(candles) < period:
            return {"upper": [], "middle": [], "lower": []}

        closes = [float(c.close) for c in candles]

        upper_band = []
        middle_band = []
        lower_band = []

        for i in range(period - 1, len(candles)):
            # Calculate SMA
            sma = sum(closes[i - period + 1 : i + 1]) / period

            # Calculate standard deviation
            variance = (
                sum((closes[j] - sma) ** 2 for j in range(i - period + 1, i + 1))
                / period
            )
            std = variance**0.5

            # Calculate bands
            upper = sma + (std_dev * std)
            lower = sma - (std_dev * std)

            timestamp = candles[i].timestamp
            metadata = {"period": period, "std_dev": std_dev}

            upper_band.append(
                IndicatorResult(value=upper, timestamp=timestamp, metadata=metadata)
            )
            middle_band.append(
                IndicatorResult(value=sma, timestamp=timestamp, metadata=metadata)
            )
            lower_band.append(
                IndicatorResult(value=lower, timestamp=timestamp, metadata=metadata)
            )

        return {
            "upper": upper_band,
            "middle": middle_band,
            "lower": lower_band,
        }

    @staticmethod
    def stochastic(
        candles: list[Candle], k_period: int = 14, d_period: int = 3
    ) -> Dict[str, list[IndicatorResult]]:
        """
        Stochastic Oscillator

        Args:
            candles: List of candles
            k_period: %K period (default 14)
            d_period: %D period (default 3)

        Returns:
            Dictionary with 'k' and 'd' keys
        ."""
        if len(candles) < k_period:
            return {"k": [], "d": []}

        k_values = []

        for i in range(k_period - 1, len(candles)):
            # Find highest high and lowest low in the period
            highs = [float(candles[j].high) for j in range(i - k_period + 1, i + 1)]
            lows = [float(candles[j].low) for j in range(i - k_period + 1, i + 1)]

            highest_high = max(highs)
            lowest_low = min(lows)
            current_close = float(candles[i].close)

            # Calculate %K
            if highest_high == lowest_low:
                k_value = 50.0
            else:
                k_value = (
                    (current_close - lowest_low) / (highest_high - lowest_low)
                ) * 100

            k_values.append(
                IndicatorResult(
                    value=k_value,
                    timestamp=candles[i].timestamp,
                    metadata={"k_period": k_period},
                )
            )

        # Calculate %D (SMA of %K)
        d_values = []
        if len(k_values) >= d_period:
            for i in range(d_period - 1, len(k_values)):
                d_value = (
                    sum(k_values[j].value for j in range(i - d_period + 1, i + 1))
                    / d_period
                )
                d_values.append(
                    IndicatorResult(
                        value=d_value,
                        timestamp=k_values[i].timestamp,
                        metadata={"d_period": d_period},
                    )
                )

        return {"k": k_values, "d": d_values}


class EMASystem:
    """
    Specialized EMA system for trend analysis.

    Handles multiple EMA calculations and provides trend analysis
    specifically for the FVG strategy requirements.
    ."""

    def __init__(
        self,
        fast_period: int = 9,
        medium_period: int = 20,
        slow_period: int = 50,
    ):
        """
        Initialize EMA system.

        Args:
            fast_period: Fast EMA period (default 9)
            medium_period: Medium EMA period (default 20)
            slow_period: Slow EMA period (default 50)
        ."""
        self.fast_period = fast_period
        self.medium_period = medium_period
        self.slow_period = slow_period

    def calculate_emas(self, candles: list[Candle]) -> Dict[str, list[IndicatorResult]]:
        """
        Calculate all EMAs for the system.

        Args:
            candles: List of candles

        Returns:
            Dictionary with 'fast', 'medium', and 'slow' EMA values
        ."""
        return {
            "fast": TechnicalIndicators.ema(candles, self.fast_period),
            "medium": TechnicalIndicators.ema(candles, self.medium_period),
            "slow": TechnicalIndicators.ema(candles, self.slow_period),
        }

    def check_ema_alignment(
        self,
        emas: Dict[str, list[IndicatorResult]],
        direction: str,
        index: int = -1,
    ) -> bool:
        """
        Check if EMAs are properly aligned for trend direction.

        Args:
            emas: Dictionary of EMA values
            direction: 'bullish' or 'bearish'
            index: Index to check (default -1 for latest)

        Returns:
            True if EMAs are aligned, False otherwise
        ."""
        if not all(key in emas for key in ["fast", "medium", "slow"]):
            return False

        if not all(len(emas[key]) > abs(index) for key in ["fast", "medium", "slow"]):
            return False

        fast_value = emas["fast"][index].value
        medium_value = emas["medium"][index].value
        slow_value = emas["slow"][index].value

        if direction.lower() == "bullish":
            # For bullish: fast > medium > slow
            return fast_value > medium_value > slow_value
        elif direction.lower() == "bearish":
            # For bearish: fast < medium < slow
            return fast_value < medium_value < slow_value

        return False

    def get_trend_strength(
        self, emas: Dict[str, list[IndicatorResult]], index: int = -1
    ) -> float:
        """
        Calculate trend strength based on EMA separation.

        Args:
            emas: Dictionary of EMA values
            index: Index to check (default -1 for latest)

        Returns:
            Trend strength score (0.0 to 1.0)
        ."""
        if not all(key in emas for key in ["fast", "medium", "slow"]):
            return 0.0

        if not all(len(emas[key]) > abs(index) for key in ["fast", "medium", "slow"]):
            return 0.0

        fast_value = emas["fast"][index].value
        medium_value = emas["medium"][index].value
        slow_value = emas["slow"][index].value

        # Calculate relative separations
        fast_medium_sep = abs(fast_value - medium_value) / medium_value
        medium_slow_sep = abs(medium_value - slow_value) / slow_value

        # Average separation as strength indicator
        avg_separation = (fast_medium_sep + medium_slow_sep) / 2

        # Normalize to 0-1 range (assuming 5% separation is maximum strength)
        return min(avg_separation / 0.05, 1.0)

    def check_consecutive_closes(
        self,
        candles: list[Candle],
        emas: Dict[str, list[IndicatorResult]],
        direction: str,
        consecutive_count: int = 2,
    ) -> bool:
        """
        Check for consecutive closes above/below medium EMA.

        Args:
            candles: List of candles
            emas: Dictionary of EMA values
            direction: 'bullish' or 'bearish'
            consecutive_count: Number of consecutive closes required

        Returns:
            True if consecutive closes condition is met
        ."""
        if "medium" not in emas or len(emas["medium"]) < consecutive_count:
            return False

        if len(candles) < consecutive_count:
            return False

        for i in range(consecutive_count):
            candle_idx = -(i + 1)
            ema_idx = -(i + 1)

            if abs(candle_idx) > len(candles) or abs(ema_idx) > len(emas["medium"]):
                return False

            close_price = float(candles[candle_idx].close)
            ema_value = emas["medium"][ema_idx].value

            if direction.lower() == "bullish":
                if close_price <= ema_value:
                    return False
            elif direction.lower() == "bearish":
                if close_price >= ema_value:
                    return False

        return True
