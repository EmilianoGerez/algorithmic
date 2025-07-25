"""Multi-timeframe candle aggregator with look-ahead bias prevention."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.entities import Candle
from core.strategy.ring_buffer import CandleBuffer
from core.strategy.timeframe import (
    format_timeframe_name,
    get_bucket_id,
)

__all__ = ["TimeAggregator", "MultiTimeframeAggregator"]


@dataclass
class TimeAggregator:
    """Single timeframe aggregator with ring buffer and look-ahead prevention.

    Aggregates 1-minute source candles into higher timeframe candles (H1, H4, D1, etc.)
    using a ring buffer for memory efficiency. Emits only completed periods to prevent
    look-ahead bias.

    Key Features:
        - O(1) insertions using ring buffer
        - Unix epoch-based period detection (no drift)
        - Look-ahead bias prevention (closed candles only)
        - Memory efficient (fixed buffer size)

    Args:
        tf_minutes: Target timeframe in minutes (60=H1, 240=H4, 1440=D1).
        source_tf_minutes: Source timeframe in minutes (typically 1).
        buffer_size: Maximum number of source candles to keep in memory.

    Example:
        >>> aggregator = TimeAggregator(tf_minutes=60)  # H1 aggregator
        >>> for minute_candle in minute_candles:
        ...     h1_candles = aggregator.update(minute_candle)
        ...     for h1_candle in h1_candles:
        ...         print(f"Completed H1: {h1_candle}")
    """

    tf_minutes: int
    source_tf_minutes: int = 1
    buffer_size: int = 1500

    # Internal state
    _buffer: CandleBuffer = field(init=False)
    _current_bucket_id: int | None = field(default=None, init=False)
    _name: str = field(init=False)

    def __post_init__(self) -> None:
        """Initialize internal state after dataclass creation."""
        if self.tf_minutes <= 0:
            raise ValueError("tf_minutes must be positive")
        if self.source_tf_minutes <= 0:
            raise ValueError("source_tf_minutes must be positive")
        if self.tf_minutes < self.source_tf_minutes:
            raise ValueError("Target timeframe must be >= source timeframe")
        if self.buffer_size <= 0:
            raise ValueError("buffer_size must be positive")

        self._buffer = CandleBuffer(maxsize=self.buffer_size)
        self._name = format_timeframe_name(self.tf_minutes)

    @property
    def name(self) -> str:
        """Human-readable name for this timeframe (e.g., 'H1', 'D1')."""
        return self._name

    @property
    def candles_per_period(self) -> int:
        """Number of source candles needed to complete one target period."""
        return self.tf_minutes // self.source_tf_minutes

    def update(self, candle: Candle) -> list[Candle]:
        """Update aggregator with new source candle.

        Returns completed target timeframe candles. Most updates return empty list;
        only when a period boundary is crossed will a completed candle be emitted.

        Args:
            candle: New source timeframe candle (typically 1-minute).

        Returns:
            List of completed target timeframe candles (0 or 1 items usually).
            Empty list if no periods completed.

        Example:
            >>> aggregator = TimeAggregator(tf_minutes=60)
            >>> result = aggregator.update(minute_candle)
            >>> if result:
            ...     h1_candle = result[0]
            ...     print(f"H1 complete: {h1_candle.close}")
        """
        bucket_id = get_bucket_id(candle.ts, self.tf_minutes)
        completed_candles: list[Candle] = []

        # Check if we're starting a new bucket (period boundary crossed)
        if self._current_bucket_id is not None and bucket_id != self._current_bucket_id:
            # We've moved to a new period - emit the completed previous period
            if len(self._buffer) > 0:  # Ensure we have data to aggregate
                completed_candle = self._create_aggregated_candle(self._current_bucket_id)
                completed_candles.append(completed_candle)

            # Clear buffer for new period (keep memory usage bounded)
            self._buffer.clear()

        # Add new candle to current period buffer
        self._buffer.append(candle)
        self._current_bucket_id = bucket_id

        return completed_candles

    def flush(self) -> list[Candle]:
        """Flush any remaining complete periods at stream end.

        Call this when the data stream ends to emit the last complete period.
        Incomplete periods are discarded to prevent look-ahead bias.

        Returns:
            List of final completed candles (0 or 1 items).

        Example:
            >>> # At end of backtest or stream
            >>> final_candles = aggregator.flush()
            >>> for candle in final_candles:
            ...     print(f"Final {aggregator.name}: {candle}")
        """
        completed_candles: list[Candle] = []

        # Only emit if we have a complete period
        if (self._current_bucket_id is not None and
            len(self._buffer) >= self.candles_per_period):
            completed_candle = self._create_aggregated_candle(self._current_bucket_id)
            completed_candles.append(completed_candle)

        # Clear state
        self._buffer.clear()
        self._current_bucket_id = None

        return completed_candles

    def _create_aggregated_candle(self, bucket_id: int) -> Candle:
        """Create aggregated candle from current buffer contents.

        Args:
            bucket_id: Bucket ID for timestamp calculation.

        Returns:
            Aggregated candle with OHLCV calculated from buffer.

        Raises:
            ValueError: If buffer is empty.
        """
        if len(self._buffer) == 0:
            raise ValueError("Cannot create aggregated candle from empty buffer")

        # Calculate OHLCV from buffer
        open_price, high_price, low_price, close_price, volume = self._buffer.get_ohlcv()

        # Calculate timestamp for start of the completed period
        bucket_start_minutes = bucket_id * self.tf_minutes
        timestamp = datetime.fromtimestamp(bucket_start_minutes * 60, tz=UTC)

        return Candle(
            ts=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume
        )

    def reset(self) -> None:
        """Reset aggregator state for new data stream.

        Clears all buffers and resets internal state. Useful when switching
        between different data sources or restarting analysis.
        """
        self._buffer.clear()
        self._current_bucket_id = None


@dataclass
class MultiTimeframeAggregator:
    """Manages multiple timeframe aggregators for parallel processing.

    Efficiently aggregates a single 1-minute stream into multiple higher timeframes
    simultaneously. Each timeframe maintains its own state and buffer.

    Args:
        timeframes_minutes: List of target timeframes in minutes.
                           Example: [60, 240, 1440] for H1, H4, D1.
        source_tf_minutes: Source timeframe in minutes (typically 1).
        buffer_size: Buffer size for each timeframe aggregator.

    Example:
        >>> aggregator = MultiTimeframeAggregator([60, 240, 1440])
        >>> results = aggregator.update(minute_candle)
        >>> for tf_name, candles in results.items():
        ...     for candle in candles:
        ...         print(f"{tf_name}: {candle.close}")
    """

    timeframes_minutes: list[int]
    source_tf_minutes: int = 1
    buffer_size: int = 1500

    # Internal state
    _aggregators: dict[str, TimeAggregator] = field(init=False)

    def __post_init__(self) -> None:
        """Initialize aggregators for each timeframe."""
        if not self.timeframes_minutes:
            raise ValueError("At least one timeframe must be specified")

        self._aggregators = {}
        for tf_minutes in self.timeframes_minutes:
            aggregator = TimeAggregator(
                tf_minutes=tf_minutes,
                source_tf_minutes=self.source_tf_minutes,
                buffer_size=self.buffer_size
            )
            self._aggregators[aggregator.name] = aggregator

    @property
    def timeframe_names(self) -> list[str]:
        """List of timeframe names being aggregated."""
        return list(self._aggregators.keys())

    def update(self, candle: Candle) -> dict[str, list[Candle]]:
        """Update all timeframe aggregators with new source candle.

        Args:
            candle: New source timeframe candle.

        Returns:
            Dictionary mapping timeframe names to lists of completed candles.
            Most timeframes will return empty lists most of the time.

        Example:
            >>> results = multi_agg.update(minute_candle)
            >>> # results = {"H1": [], "H4": [h4_candle], "D1": []}
        """
        results: dict[str, list[Candle]] = {}

        for tf_name, aggregator in self._aggregators.items():
            completed_candles = aggregator.update(candle)
            results[tf_name] = completed_candles

        return results

    def flush_all(self) -> dict[str, list[Candle]]:
        """Flush all aggregators at stream end.

        Returns:
            Dictionary mapping timeframe names to final completed candles.
        """
        results: dict[str, list[Candle]] = {}

        for tf_name, aggregator in self._aggregators.items():
            completed_candles = aggregator.flush()
            results[tf_name] = completed_candles

        return results

    def reset_all(self) -> None:
        """Reset all aggregators for new data stream."""
        for aggregator in self._aggregators.values():
            aggregator.reset()
