"""Enhanced FVG detector with ATR-scaled gaps and volume filtering.

See :ref:`design_notebook:Initial Implementation Sprint Plan`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from core.entities import Candle


@dataclass
class FVGEvent:
    """FVG detection event with enhanced metadata."""

    ts: datetime
    pool_id: str
    side: str  # "bullish" or "bearish" gap direction
    top: float
    bottom: float
    tf: str
    strength: float  # 0.0-1.0 normalized strength
    volume_ratio: float  # Relative to volume SMA
    gap_size_atr: float  # Gap size in ATR units
    gap_size_pct: float  # Gap size as percentage


class FVGDetector:
    """Enhanced FVG detector with ATR scaling and volume filtering.

    Uses dependency injection for indicators to avoid global imports.
    Implements OR logic for gap size validation (ATR or percentage).
    """

    def __init__(
        self,
        tf: str,
        min_gap_atr: float = 0.3,
        min_gap_pct: float = 0.05,
        min_rel_vol: float = 1.2,
    ):
        """Initialize FVG detector with configurable thresholds.

        Args:
            tf: Timeframe identifier (e.g., "H1", "H4", "D1").
            min_gap_atr: Minimum gap size in ATR units.
            min_gap_pct: Minimum gap size as percentage of price.
            min_rel_vol: Minimum volume relative to SMA baseline.
        """
        self.tf = tf
        self.min_gap_atr = min_gap_atr
        self.min_gap_pct = min_gap_pct
        self.min_rel_vol = min_rel_vol
        self._buffer: list[Candle] = []

    def update(
        self, candle: Candle, atr_value: float, vol_sma_value: float
    ) -> list[FVGEvent]:
        """Detect FVGs using ATR scaling and volume validation.

        Args:
            candle: New HTF candle to process.
            atr_value: Current ATR value for gap scaling.
            vol_sma_value: Volume SMA baseline for filtering.

        Returns:
            List of FVG events (0-2 per update).
        """
        self._buffer.append(candle)

        # Need 3 candles for FVG detection
        if len(self._buffer) < 3:
            return []

        # Keep buffer size at 3 for memory efficiency
        if len(self._buffer) > 3:
            self._buffer = self._buffer[-3:]

        prev, _, next_candle = self._buffer[-3], self._buffer[-2], self._buffer[-1]
        events = []

        # Calculate relative volume for filtering
        rel_vol = next_candle.volume / vol_sma_value if vol_sma_value > 0 else 0

        # Volume filter: skip low-volume gaps
        if rel_vol < self.min_rel_vol:
            return []

        # Bullish FVG: prev.high < next.low (gap up)
        if prev.high < next_candle.low:
            gap_size = next_candle.low - prev.high
            gap_size_atr = gap_size / atr_value if atr_value > 0 else 0
            gap_size_pct = gap_size / prev.close if prev.close > 0 else 0

            # OR logic: pass if either ATR or percentage threshold met
            if gap_size_atr >= self.min_gap_atr or gap_size_pct >= self.min_gap_pct:
                strength = min(1.0, max(gap_size_atr / 2.0, gap_size_pct * 10))

                events.append(
                    FVGEvent(
                        ts=next_candle.ts,
                        pool_id=str(uuid4()),
                        side="bullish",
                        top=next_candle.low,
                        bottom=prev.high,
                        tf=self.tf,
                        strength=strength,
                        volume_ratio=rel_vol,
                        gap_size_atr=gap_size_atr,
                        gap_size_pct=gap_size_pct,
                    )
                )

        # Bearish FVG: prev.low > next.high (gap down)
        if prev.low > next_candle.high:
            gap_size = prev.low - next_candle.high
            gap_size_atr = gap_size / atr_value if atr_value > 0 else 0
            gap_size_pct = gap_size / prev.close if prev.close > 0 else 0

            # OR logic: pass if either ATR or percentage threshold met
            if gap_size_atr >= self.min_gap_atr or gap_size_pct >= self.min_gap_pct:
                strength = min(1.0, max(gap_size_atr / 2.0, gap_size_pct * 10))

                events.append(
                    FVGEvent(
                        ts=next_candle.ts,
                        pool_id=str(uuid4()),
                        side="bearish",
                        top=prev.low,
                        bottom=next_candle.high,
                        tf=self.tf,
                        strength=strength,
                        volume_ratio=rel_vol,
                        gap_size_atr=gap_size_atr,
                        gap_size_pct=gap_size_pct,
                    )
                )

        return events
