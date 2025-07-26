"""Shared utilities for HTF pattern detectors.

Common helper functions to avoid duplication across detector implementations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.entities import Candle

logger = logging.getLogger(__name__)


def calculate_gap_metrics(
    prev_candle: Candle,
    next_candle: Candle,
    atr_value: float,
    gap_type: str = "bullish",
) -> tuple[float, float, float]:
    """Calculate gap size in absolute, ATR-scaled, and percentage terms for FVG detection.

    Args:
        prev_candle: Previous candle in sequence.
        next_candle: Next candle in sequence (after gap).
        atr_value: Current ATR value for scaling.
        gap_type: "bullish" or "bearish" gap type.

    Returns:
        Tuple of (gap_size, gap_size_atr, gap_size_pct).
    """
    if gap_type == "bullish":
        # Bullish gap: prev.high < next.low
        gap_size = next_candle.low - prev_candle.high
        reference_price = prev_candle.close
    else:
        # Bearish gap: prev.low > next.high
        gap_size = prev_candle.low - next_candle.high
        reference_price = prev_candle.close

    # Calculate ATR-scaled gap size
    gap_size_atr = gap_size / atr_value if atr_value > 0 else 0.0

    # Calculate percentage gap size
    gap_size_pct = gap_size / reference_price if reference_price > 0 else 0.0

    return gap_size, gap_size_atr, gap_size_pct


def calculate_volume_ratio(current_volume: float, volume_sma: float) -> float:
    """Calculate volume ratio relative to SMA baseline for filtering.

    Args:
        current_volume: Current candle volume.
        volume_sma: Volume SMA baseline value.

    Returns:
        Volume ratio (current / SMA).
    """
    return current_volume / volume_sma if volume_sma > 0 else 0.0


def normalize_strength(
    primary_metric: float,
    secondary_metric: float,
    primary_scale: float = 2.0,
    secondary_scale: float = 10.0,
) -> float:
    """Normalize dual metrics to 0.0-1.0 strength range using max of scaled values.

    Args:
        primary_metric: Primary strength metric (e.g., ATR distance).
        secondary_metric: Secondary strength metric (e.g., percentage).
        primary_scale: Scale factor for primary metric.
        secondary_scale: Scale factor for secondary metric.

    Returns:
        Normalized strength value between 0.0 and 1.0.
    """
    primary_strength = primary_metric / primary_scale
    secondary_strength = secondary_metric * secondary_scale
    return min(1.0, max(primary_strength, secondary_strength))


def log_detection_skip(
    detector_name: str,
    reason: str,
    candle_ts: str,
    tf: str,
    additional_info: str = "",
) -> None:
    """Log debug information when pattern detection is skipped (conditional for performance).

    Args:
        detector_name: Name of the detector (e.g., "FVG", "Pivot").
        reason: Reason for skipping detection.
        candle_ts: Candle timestamp for reference.
        tf: Timeframe identifier.
        additional_info: Additional context information.
    """
    # Only construct log message if debug logging is enabled
    if logger.isEnabledFor(logging.DEBUG):
        info_str = f" ({additional_info})" if additional_info else ""
        logger.debug(
            "%s detection skipped for %s at %s: %s%s",
            detector_name,
            tf,
            candle_ts,
            reason,
            info_str,
        )


def validate_candle_sequence(candles: list[Candle], min_count: int = 3) -> bool:
    """Validate candle sequence has sufficient count and chronological ordering.

    Args:
        candles: List of candles to validate.
        min_count: Minimum required candle count.

    Returns:
        True if sequence is valid, False otherwise.
    """
    if len(candles) < min_count:
        return False

    # Check chronological ordering
    for i in range(1, len(candles)):
        if candles[i].ts <= candles[i - 1].ts:
            logger.warning(
                f"Out-of-order candles detected: {candles[i - 1].ts} >= {candles[i].ts}"
            )
            return False

    return True
