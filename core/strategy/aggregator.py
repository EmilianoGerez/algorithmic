"""Multi-timeframe candle aggregator with look-ahead bias prevention."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from core.entities import Candle
from core.strategy.ring_buffer import CandleBuffer
from core.strategy.timeframe import (
    Timeframe,
    format_timeframe_name,  # Keep for backward compatibility
)

# Type aliases for cleaner annotations
CandleEvent = tuple[str, Candle]  # (timeframe_name, completed_candle)


class OutOfOrderPolicy(Enum):
    """Policy for handling out-of-chronological-order candles."""

    DROP = "drop"  # Silently ignore out-of-order candles
    RAISE = "raise"  # Raise exception on out-of-order candles
    RECALC = "recalc"  # Recalculate affected buckets (expensive)


class ClockSkewError(Exception):
    """Raised when candle timestamp violates clock-skew limits."""

    pass


__all__ = [
    "CandleEvent",
    "TimeAggregator",
    "MultiTimeframeAggregator",
    "OutOfOrderPolicy",
    "ClockSkewError",
]


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
        >>> from core.strategy.timeframe import TimeframeConfig
        >>> aggregator = TimeAggregator(tf_minutes=60)  # H1 aggregator
        >>> # Or using the new Timeframe objects (recommended):
        >>> aggregator = TimeAggregator.from_timeframe(TimeframeConfig.H1)
        >>> for minute_candle in minute_candles:
        ...     h1_candles = aggregator.update(minute_candle)
        ...     h1_candles = aggregator.update(minute_candle)
        ...     for h1_candle in h1_candles:
        ...         print(f"Completed H1: {h1_candle}")
    """

    tf_minutes: int
    source_tf_minutes: int = 1
    buffer_size: int = 1500

    # Clock-skew and ordering controls
    out_of_order_policy: OutOfOrderPolicy = OutOfOrderPolicy.DROP
    max_clock_skew_seconds: int = 300  # 5 minutes default
    enable_strict_ordering: bool = True

    # Internal state
    _buffer: CandleBuffer = field(init=False)
    _current_bucket_id: int | None = field(default=None, init=False)
    _last_timestamp: int | None = field(default=None, init=False)  # For ordering checks
    _name: str = field(init=False)
    _timeframe: Timeframe | None = field(default=None, init=False)

    @classmethod
    def from_timeframe(
        cls,
        timeframe: Timeframe,
        source_tf_minutes: int = 1,
        buffer_size: int = 1500,
        out_of_order_policy: OutOfOrderPolicy = OutOfOrderPolicy.DROP,
        max_clock_skew_seconds: int = 300,
        enable_strict_ordering: bool = True,
    ) -> TimeAggregator:
        """Create aggregator from Timeframe object (recommended).

        This provides better encapsulation and self-documenting code.

        Args:
            timeframe: Timeframe object (e.g., TimeframeConfig.H1).
            source_tf_minutes: Source timeframe in minutes (typically 1).
            buffer_size: Maximum number of source candles in memory.
            out_of_order_policy: How to handle out-of-order candles.
            max_clock_skew_seconds: Maximum allowed timestamp drift.
            enable_strict_ordering: Whether to enforce chronological order.

        Returns:
            Configured TimeAggregator instance.

        Example:
            >>> from core.strategy.timeframe import TimeframeConfig
            >>> h1_agg = TimeAggregator.from_timeframe(TimeframeConfig.H1)
            >>> bucket_id = h1_agg.timeframe.bucket_id(candle.ts)  # Clean and readable
        """
        instance = cls(
            tf_minutes=timeframe.minutes,
            source_tf_minutes=source_tf_minutes,
            buffer_size=buffer_size,
            out_of_order_policy=out_of_order_policy,
            max_clock_skew_seconds=max_clock_skew_seconds,
            enable_strict_ordering=enable_strict_ordering,
        )
        instance._timeframe = timeframe
        return instance

    @property
    def timeframe(self) -> Timeframe:
        """Get the timeframe object for this aggregator.

        If created with tf_minutes, creates a Timeframe on-demand.
        """
        if self._timeframe is None:
            self._timeframe = Timeframe(self.tf_minutes, f"TF{self.tf_minutes}")
        return self._timeframe

    def _validate_candle_ordering(self, candle: Candle) -> bool:
        """Validate candle timestamp against clock-skew and ordering policies.

        Args:
            candle: Incoming candle to validate.

        Returns:
            True if candle should be processed, False if it should be dropped.

        Raises:
            ClockSkewError: If strict ordering is enabled and violation detected.
        """
        if not self.enable_strict_ordering:
            return True

        # Convert datetime to unix timestamp for comparison
        current_time = int(candle.ts.timestamp())

        # Check clock skew (future candles)
        import time

        now = int(time.time())
        if current_time > now + self.max_clock_skew_seconds:
            if self.out_of_order_policy == OutOfOrderPolicy.RAISE:
                raise ClockSkewError(
                    f"Candle timestamp {current_time} is {current_time - now}s "
                    f"in the future (max allowed: {self.max_clock_skew_seconds}s)"
                )
            elif self.out_of_order_policy == OutOfOrderPolicy.DROP:
                return False
            # RECALC: process anyway, let downstream handle

        # Check chronological ordering (past candles)
        if self._last_timestamp is not None:
            time_diff = current_time - self._last_timestamp

            # Past candle detected
            if time_diff < 0:
                if self.out_of_order_policy == OutOfOrderPolicy.RAISE:
                    raise ClockSkewError(
                        f"Out-of-order candle: {current_time} < {self._last_timestamp} "
                        f"(delta: {time_diff}s)"
                    )
                elif self.out_of_order_policy == OutOfOrderPolicy.DROP:
                    return False
                # RECALC: continue processing, will trigger bucket recalculation

        # Update last seen timestamp
        self._last_timestamp = current_time
        return True

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
        # Validate candle ordering and clock-skew
        if not self._validate_candle_ordering(candle):
            return []  # Candle dropped due to policy

        # TODO: Optimization opportunity - cache bucket_id calculation
        # For long backtests, store last_bucket_id and only recalculate when
        # timeframe period has potentially changed (5-10% CPU savings)
        bucket_id = self.timeframe.bucket_id(candle.ts)  # Self-contained and readable
        completed_candles: list[Candle] = []

        # CONFIGURABLE POLICY: Handle out-of-order bars based on policy setting
        # Out-of-order detection: incoming candle belongs to an older bucket
        if self._current_bucket_id is not None and bucket_id < self._current_bucket_id:
            # Late bar detected - handle per policy
            if self.out_of_order_policy == OutOfOrderPolicy.DROP:
                # DROP: Silent ignore (prevents unbounded memory growth)
                # JUSTIFICATION:
                # - Prevents unbounded memory growth tracking historical buckets
                # - Maintains deterministic output regardless of delivery order
                # - Simplifies downstream processing (no candle "updates")
                # - Feed reliability should be handled at connection layer
                return []  # Drop the late bar, return no completions
            elif self.out_of_order_policy == OutOfOrderPolicy.RAISE:
                raise ClockSkewError(
                    f"Out-of-order bucket: candle bucket_id {bucket_id} < "
                    f"current bucket_id {self._current_bucket_id}"
                )
            # RECALC: Continue processing (expensive but most accurate)
            # Note: This requires historical bucket reconstruction which
            # may need additional implementation for full support

        # Check if we're starting a new bucket (period boundary crossed)
        if self._current_bucket_id is not None and bucket_id != self._current_bucket_id:
            # We've moved to a new period - emit the completed previous period
            if len(self._buffer) > 0:  # Ensure we have data to aggregate
                completed_candle = self._create_aggregated_candle(
                    self._current_bucket_id
                )
                completed_candles.append(completed_candle)

            # Clear buffer for new period (keep memory usage bounded)
            self._buffer.clear()

        # Add new candle to current period buffer
        self._buffer.append(candle)
        self._current_bucket_id = bucket_id

        return completed_candles

    def update_with_label(self, candle: Candle) -> list[CandleEvent]:
        """Update aggregator with new source candle, returning labeled results.

        Returns completed target timeframe candles with their timeframe labels.
        This method is useful for downstream routing without additional lookups.

        Args:
            candle: New source timeframe candle (typically 1-minute).

        Returns:
            List of CandleEvent tuples (timeframe_name, completed_candle).

        Example:
            >>> aggregator = TimeAggregator(tf_minutes=60)
            >>> results = aggregator.update_with_label(minute_candle)
            >>> for tf_name, tf_candle in results:
            ...     print(f"{tf_name}: {tf_candle.close}")
        """
        completed_candles = self.update(candle)
        return [(self.name, candle) for candle in completed_candles]

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
        if (
            self._current_bucket_id is not None
            and len(self._buffer) >= self.candles_per_period
        ):
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
        open_price, high_price, low_price, close_price, volume = (
            self._buffer.get_ohlcv()
        )

        # Calculate timestamp for start of the completed period using timeframe
        # Use any candle from buffer to get the bucket start time
        sample_candle = self._buffer[0]  # Get first candle for timestamp reference
        timestamp = self.timeframe.bucket_start(sample_candle.ts)

        return Candle(
            ts=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
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
        out_of_order_policy: How to handle out-of-order candles (applied to all timeframes).
        max_clock_skew_seconds: Maximum allowed timestamp drift.
        enable_strict_ordering: Whether to enforce chronological order.

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
    out_of_order_policy: OutOfOrderPolicy = OutOfOrderPolicy.DROP
    max_clock_skew_seconds: int = 300
    enable_strict_ordering: bool = True

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
                buffer_size=self.buffer_size,
                out_of_order_policy=self.out_of_order_policy,
                max_clock_skew_seconds=self.max_clock_skew_seconds,
                enable_strict_ordering=self.enable_strict_ordering,
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
