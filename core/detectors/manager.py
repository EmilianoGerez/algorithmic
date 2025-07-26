"""DetectorManager service for coordinating multi-timeframe HTF detection.

See :ref:`design_notebook:Initial Implementation Sprint Plan`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from core.detectors.events import LiquidityPoolEvent
from core.detectors.fvg import FVGDetector
from core.detectors.pivot import PivotDetector
from core.entities import Candle
from core.indicators.atr import ATRIndicator
from core.indicators.volume_sma import VolumeSMAIndicator


@dataclass
class DetectorConfig:
    """Configuration for detector parameters."""

    # FVG settings
    fvg_min_gap_atr: float = 0.3
    fvg_min_gap_pct: float = 0.05
    fvg_min_rel_vol: float = 1.2

    # Pivot settings
    pivot_lookback: int = 5
    pivot_min_sigma: float = 0.5

    # ATR settings
    atr_period: int = 14

    # Volume SMA settings
    volume_sma_period: int = 20

    # Ordering policy
    out_of_order_policy: str = "drop"  # "drop" or "raise"

    # Enabled timeframes
    enabled_timeframes: list[str] = field(default_factory=lambda: ["H1", "H4", "D1"])


class DetectorManager:
    """Coordinates HTF pattern detection across multiple timeframes.

    Processes HTF candles sequentially (H1 → H4 → D1) and maintains
    per-timeframe state for each detector type. Uses dependency injection
    for indicators to avoid global imports.
    """

    def __init__(self, config: DetectorConfig | None = None):
        """Initialize detector manager with configuration.

        Args:
            config: Detector configuration. Uses defaults if None.
        """
        self.config = config or DetectorConfig()

        # Initialize detectors for each timeframe
        self._fvg_detectors: dict[str, FVGDetector] = {}
        self._pivot_detectors: dict[str, PivotDetector] = {}

        # Initialize indicators for each timeframe
        self._atr_indicators: dict[str, ATRIndicator] = {}
        self._volume_sma_indicators: dict[str, VolumeSMAIndicator] = {}

        for tf in self.config.enabled_timeframes:
            # FVG detector
            self._fvg_detectors[tf] = FVGDetector(
                tf=tf,
                min_gap_atr=self.config.fvg_min_gap_atr,
                min_gap_pct=self.config.fvg_min_gap_pct,
                min_rel_vol=self.config.fvg_min_rel_vol,
            )

            # Pivot detector
            self._pivot_detectors[tf] = PivotDetector(
                tf=tf,
                lookback_periods=self.config.pivot_lookback,
                min_sigma=self.config.pivot_min_sigma,
            )

            # ATR indicator
            self._atr_indicators[tf] = ATRIndicator(period=self.config.atr_period)

            # Volume SMA indicator
            self._volume_sma_indicators[tf] = VolumeSMAIndicator(
                period=self.config.volume_sma_period
            )

    def update(self, htf_label: str, candle: Candle) -> list[LiquidityPoolEvent]:
        """Process HTF candle and return detected events.

        Args:
            htf_label: Timeframe label (e.g., "H1", "H4", "D1").
            candle: HTF candle to process.

        Returns:
            List of liquidity pool events detected in this candle.
        """
        if htf_label not in self.config.enabled_timeframes:
            return []

        # Check for out-of-order candles
        fvg_detector = self._fvg_detectors[htf_label]
        if fvg_detector._buffer and candle.ts <= fvg_detector._buffer[-1].ts:
            if self.config.out_of_order_policy == "raise":
                raise ValueError(
                    f"Out-of-order candle in {htf_label}: "
                    f"{candle.ts} <= {fvg_detector._buffer[-1].ts}"
                )
            elif self.config.out_of_order_policy == "drop":
                # Silently drop out-of-order candle
                return []

        # Update indicators first
        self._atr_indicators[htf_label].update(candle)
        self._volume_sma_indicators[htf_label].update(candle)

        # Always update detector buffers (they need candle history)
        # But only run detection logic when indicators are ready
        events: list[LiquidityPoolEvent] = []

        # Get current indicator values
        atr_value = self._atr_indicators[htf_label].value
        vol_sma_value = self._volume_sma_indicators[htf_label].value

        if atr_value is not None and vol_sma_value is not None:
            # Indicators ready - run full detection

            # Run FVG detection
            fvg_events = self._fvg_detectors[htf_label].update(
                candle, atr_value, vol_sma_value
            )
            events.extend(fvg_events)

            # Run Pivot detection
            pivot_events = self._pivot_detectors[htf_label].update(candle, atr_value)
            events.extend(cast(list[LiquidityPoolEvent], pivot_events))
        else:
            # Indicators not ready - just update buffers without detection
            # This ensures detectors maintain proper candle history
            self._fvg_detectors[htf_label]._buffer.append(candle)
            self._pivot_detectors[htf_label]._buffer.append(candle)

        return events

    def get_detector_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all detectors."""
        stats = {}

        for tf in self.config.enabled_timeframes:
            tf_stats = {}

            # ATR stats
            atr_indicator = self._atr_indicators[tf]
            tf_stats["atr_value"] = atr_indicator.value
            tf_stats["atr_ready"] = atr_indicator.value is not None

            # Volume SMA stats
            vol_sma_indicator = self._volume_sma_indicators[tf]
            tf_stats["vol_sma_value"] = vol_sma_indicator.value
            tf_stats["vol_sma_ready"] = vol_sma_indicator.value is not None

            # Detector buffer sizes
            tf_stats["fvg_buffer_size"] = len(self._fvg_detectors[tf]._buffer)
            tf_stats["pivot_buffer_size"] = len(self._pivot_detectors[tf]._buffer)

            stats[tf] = tf_stats

        return stats

    def reset_timeframe(self, tf: str) -> None:
        """Reset all detectors and indicators for a timeframe."""
        if tf not in self.config.enabled_timeframes:
            return

        # Reinitialize detectors
        self._fvg_detectors[tf] = FVGDetector(
            tf=tf,
            min_gap_atr=self.config.fvg_min_gap_atr,
            min_gap_pct=self.config.fvg_min_gap_pct,
            min_rel_vol=self.config.fvg_min_rel_vol,
        )

        self._pivot_detectors[tf] = PivotDetector(
            tf=tf,
            lookback_periods=self.config.pivot_lookback,
            min_sigma=self.config.pivot_min_sigma,
        )

        # Reinitialize indicators
        self._atr_indicators[tf] = ATRIndicator(period=self.config.atr_period)

        self._volume_sma_indicators[tf] = VolumeSMAIndicator(
            period=self.config.volume_sma_period
        )

    def reset_all(self) -> None:
        """Reset all detectors and indicators."""
        for tf in self.config.enabled_timeframes:
            self.reset_timeframe(tf)
