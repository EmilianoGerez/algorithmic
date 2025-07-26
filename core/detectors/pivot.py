"""Pivot point detector with multi-strength classification.

See :ref:`design_notebook:Initial Implementation Sprint Plan`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from core.entities import Candle


@dataclass(frozen=True, slots=True)
class PivotEvent:
    """Pivot point event with strength classification."""

    ts: datetime
    pool_id: str
    side: str  # "high" or "low"
    price: float
    top: float  # For compatibility with LiquidityPoolEvent
    bottom: float  # For compatibility with LiquidityPoolEvent
    tf: str
    strength: float  # Normalized 0.0-1.0 for compatibility (was strength_value)
    atr_distance: float  # Distance from surrounding pivots in ATR units
    lookback_periods: int  # Number of periods used for detection
    strength_label: str  # "regular", "significant", "major"


class PivotDetector:
    """Pivot point detector with configurable lookback and ATR-based strength.

    Detects swing highs and lows using N-period lookback window.
    Classifies strength based on ATR distance from surrounding points.
    """

    def __init__(
        self,
        tf: str,
        lookback_periods: int = 5,
        min_sigma: float = 0.5,
    ):
        """Initialize pivot detector with configurable parameters.

        Args:
            tf: Timeframe identifier (e.g., "H1", "H4", "D1").
            lookback_periods: Number of candles to look back (3-10).
            min_sigma: Minimum ATR distance for pivot confirmation.
        """
        if not 2 <= lookback_periods <= 10:
            raise ValueError("lookback_periods must be between 2 and 10")

        self.tf = tf
        self.lookback_periods = lookback_periods
        self.min_sigma = min_sigma
        self._buffer: list[Candle] = []

    def update(self, candle: Candle, atr_value: float) -> list[PivotEvent]:
        """Detect pivot points using lookback window and ATR classification.

        Args:
            candle: New HTF candle to process.
            atr_value: Current ATR value for strength classification.

        Returns:
            List of pivot events (0-2 per update).
        """
        self._buffer.append(candle)

        # Need (2 * lookback + 1) candles for proper pivot detection
        min_candles = 2 * self.lookback_periods + 1
        if len(self._buffer) < min_candles:
            return []

        # Keep buffer size manageable
        max_buffer_size = min_candles + 10
        if len(self._buffer) > max_buffer_size:
            self._buffer = self._buffer[-max_buffer_size:]

        events = []

        # Check for pivot at the center of lookback window
        # This ensures we have equal periods before and after the potential pivot
        pivot_index = len(self._buffer) - self.lookback_periods - 1

        if pivot_index >= self.lookback_periods:
            pivot_candle = self._buffer[pivot_index]

            # Get surrounding candles for comparison
            left_candles = self._buffer[
                pivot_index - self.lookback_periods : pivot_index
            ]
            right_candles = self._buffer[
                pivot_index + 1 : pivot_index + self.lookback_periods + 1
            ]

            # Detect swing high
            if self._is_swing_high(pivot_candle, left_candles, right_candles):
                atr_distance = self._calculate_atr_distance(
                    pivot_candle.high,
                    left_candles + right_candles,
                    atr_value,
                    is_high=True,
                )

                if atr_distance >= self.min_sigma:
                    strength_label, strength_value = self._classify_strength(
                        atr_distance
                    )

                    events.append(
                        PivotEvent(
                            ts=pivot_candle.ts,
                            pool_id=str(uuid4()),
                            side="high",
                            price=pivot_candle.high,
                            top=pivot_candle.high,
                            bottom=pivot_candle.high,  # For high pivots, top and bottom are the same
                            tf=self.tf,
                            strength=strength_value,
                            atr_distance=atr_distance,
                            lookback_periods=self.lookback_periods,
                            strength_label=strength_label,
                        )
                    )

            # Detect swing low
            if self._is_swing_low(pivot_candle, left_candles, right_candles):
                atr_distance = self._calculate_atr_distance(
                    pivot_candle.low,
                    left_candles + right_candles,
                    atr_value,
                    is_high=False,
                )

                if atr_distance >= self.min_sigma:
                    strength_label, strength_value = self._classify_strength(
                        atr_distance
                    )

                    events.append(
                        PivotEvent(
                            ts=pivot_candle.ts,
                            pool_id=str(uuid4()),
                            side="low",
                            price=pivot_candle.low,
                            top=pivot_candle.low,  # For low pivots, top and bottom are the same
                            bottom=pivot_candle.low,
                            tf=self.tf,
                            strength=strength_value,
                            atr_distance=atr_distance,
                            lookback_periods=self.lookback_periods,
                            strength_label=strength_label,
                        )
                    )

        return events

    def _is_swing_high(
        self, pivot: Candle, left_candles: list[Candle], right_candles: list[Candle]
    ) -> bool:
        """Check if candle is a swing high."""
        pivot_high = pivot.high

        # Must be higher than all left candles
        if not all(candle.high < pivot_high for candle in left_candles):
            return False

        # Must be higher than all right candles
        return all(candle.high < pivot_high for candle in right_candles)

    def _is_swing_low(
        self, pivot: Candle, left_candles: list[Candle], right_candles: list[Candle]
    ) -> bool:
        """Check if candle is a swing low."""
        pivot_low = pivot.low

        # Must be lower than all left candles
        if not all(candle.low > pivot_low for candle in left_candles):
            return False

        # Must be lower than all right candles
        return all(candle.low > pivot_low for candle in right_candles)

    def _calculate_atr_distance(
        self,
        pivot_price: float,
        surrounding_candles: list[Candle],
        atr_value: float,
        is_high: bool,
    ) -> float:
        """Calculate ATR distance from surrounding price levels."""
        if atr_value <= 0 or not surrounding_candles:
            return 0.0

        if is_high:
            # For highs, measure distance to highest surrounding high
            max_surrounding_high = max(c.high for c in surrounding_candles)
            distance = pivot_price - max_surrounding_high
        else:
            # For lows, measure distance to lowest surrounding low
            min_surrounding_low = min(c.low for c in surrounding_candles)
            distance = min_surrounding_low - pivot_price

        return distance / atr_value

    def _classify_strength(self, atr_distance: float) -> tuple[str, float]:
        """Classify pivot strength based on ATR distance.

        Returns:
            Tuple of (strength_label, normalized_value)
        """
        if atr_distance >= 1.0:
            return "major", min(1.0, atr_distance / 2.0)
        elif atr_distance >= 0.5:
            return "significant", atr_distance / 1.0
        else:
            return "regular", atr_distance / 0.5
