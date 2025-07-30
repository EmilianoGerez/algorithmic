"""
Real-time metrics collection and latency profiling for backtesting.

This module provides comprehensive metrics collection including:
- Execution latency profiling with microsecond precision
- Memory usage tracking
- Trade and performance metrics aggregation
- Real-time streaming metrics for long-running backtests
"""

from __future__ import annotations

import logging
import time
import tracemalloc
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LatencyMeasurement:
    """Single latency measurement with context."""

    operation: str
    duration_us: float  # microseconds
    timestamp: datetime
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""

    current_mb: float
    peak_mb: float
    timestamp: datetime


@dataclass
class TradeMetrics:
    """Trade execution metrics."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_fees: float = 0.0
    max_drawdown: float = 0.0
    max_position_size: float = 0.0
    avg_trade_duration_minutes: float = 0.0


class LatencyProfiler:
    """High-precision latency profiler for backtesting operations."""

    def __init__(self, max_samples: int = 10000):
        """Initialize profiler with sample limit.

        Args:
            max_samples: Maximum samples to keep in memory per operation
        """
        self.measurements: dict[str, deque[LatencyMeasurement]] = defaultdict(
            lambda: deque(maxlen=max_samples)
        )
        self.operation_stack: list[
            tuple[str, float, dict[str, Any]]
        ] = []  # Stack for nested operations

    @contextmanager
    def measure(self, operation: str, **context: Any) -> Iterator[None]:
        """Context manager for measuring operation latency.

        Args:
            operation: Name of the operation being measured
            **context: Additional context to store with measurement

        Example:
            with profiler.measure("candle_processing", symbol="BTCUSDT"):
                process_candle(candle)
        """
        start_time = time.perf_counter()
        start_timestamp = datetime.now()

        # Push to stack for nested tracking
        self.operation_stack.append((operation, start_time, dict(context)))

        try:
            yield
        finally:
            end_time = time.perf_counter()

            # Pop from stack
            if self.operation_stack:
                op_name, op_start, op_context = self.operation_stack.pop()
                if op_name == operation:  # Sanity check
                    duration_us = (end_time - op_start) * 1_000_000

                    measurement = LatencyMeasurement(
                        operation=operation,
                        duration_us=duration_us,
                        timestamp=start_timestamp,
                        context=op_context,
                    )

                    self.measurements[operation].append(measurement)

    def get_stats(self, operation: str) -> dict[str, float]:
        """Get statistical summary for an operation.

        Args:
            operation: Operation name

        Returns:
            Dictionary with min, max, mean, p95, p99 latencies in microseconds
        """
        if operation not in self.measurements:
            return {}

        durations = [m.duration_us for m in self.measurements[operation]]
        if not durations:
            return {}

        durations.sort()
        n = len(durations)

        return {
            "count": n,
            "min_us": durations[0],
            "max_us": durations[-1],
            "mean_us": sum(durations) / n,
            "p50_us": durations[n // 2],
            "p95_us": durations[int(n * 0.95)] if n > 20 else durations[-1],
            "p99_us": durations[int(n * 0.99)] if n > 100 else durations[-1],
        }

    def get_all_stats(self) -> dict[str, dict[str, float]]:
        """Get statistics for all measured operations."""
        return {op: self.get_stats(op) for op in self.measurements}

    def reset(self) -> None:
        """Clear all measurements."""
        self.measurements.clear()
        self.operation_stack.clear()


class MemoryTracker:
    """Memory usage tracking for backtesting processes."""

    def __init__(self, enable_tracing: bool = True):
        """Initialize memory tracker.

        Args:
            enable_tracing: Whether to enable detailed memory tracing
        """
        self.enable_tracing = enable_tracing
        self.snapshots: list[MemorySnapshot] = []
        self.peak_memory = 0.0

        if enable_tracing:
            tracemalloc.start()

    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory usage snapshot.

        Returns:
            MemorySnapshot with current and peak usage
        """
        if self.enable_tracing:
            current, peak = tracemalloc.get_traced_memory()
            current_mb = current / 1024 / 1024
            peak_mb = peak / 1024 / 1024
        else:
            # Fallback to basic memory info if available
            try:
                import psutil

                process = psutil.Process()
                memory_info = process.memory_info()
                current_mb = memory_info.rss / 1024 / 1024
                peak_mb = max(self.peak_memory, current_mb)
                self.peak_memory = peak_mb
            except ImportError:
                current_mb = peak_mb = 0.0

        snapshot = MemorySnapshot(
            current_mb=current_mb, peak_mb=peak_mb, timestamp=datetime.now()
        )

        self.snapshots.append(snapshot)
        return snapshot

    def get_peak_usage(self) -> float:
        """Get peak memory usage in MB."""
        if self.snapshots:
            return max(s.peak_mb for s in self.snapshots)
        return 0.0

    def stop_tracing(self) -> None:
        """Stop memory tracing."""
        if self.enable_tracing:
            tracemalloc.stop()


class MetricsCollector:
    """Comprehensive metrics collection for backtesting runs."""

    def __init__(
        self, enable_latency_profiling: bool = True, enable_memory_tracking: bool = True
    ):
        """Initialize metrics collector.

        Args:
            enable_latency_profiling: Whether to enable latency profiling
            enable_memory_tracking: Whether to enable memory tracking
        """
        self.latency_profiler = LatencyProfiler() if enable_latency_profiling else None
        self.memory_tracker = MemoryTracker() if enable_memory_tracking else None
        self.trade_metrics = TradeMetrics()
        self.custom_metrics: dict[str, Any] = {}
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

        # New metric counters for real-time dashboards
        self.liquidity_pools_created_total: int = 0
        self.signals_emitted_total: int = 0
        self.trades_win_total: int = 0
        self.trades_loss_total: int = 0

    def start_collection(self) -> None:
        """Start metrics collection."""
        self.start_time = datetime.now()
        logger.info("Metrics collection started")

    def stop_collection(self) -> None:
        """Stop metrics collection."""
        self.end_time = datetime.now()
        if self.memory_tracker:
            self.memory_tracker.stop_tracing()
        logger.info("Metrics collection stopped")

    @contextmanager
    def measure_latency(self, operation: str, **context: Any) -> Iterator[None]:
        """Context manager for latency measurement.

        Args:
            operation: Operation name
            **context: Additional context
        """
        if self.latency_profiler:
            with self.latency_profiler.measure(operation, **context):
                yield
        else:
            yield

    def record_trade(
        self, pnl: float, fees: float, duration_minutes: float, position_size: float
    ) -> None:
        """Record trade execution metrics.

        Args:
            pnl: Profit/loss for the trade
            fees: Trading fees paid
            duration_minutes: Trade duration in minutes
            position_size: Position size (absolute value)
        """
        self.trade_metrics.total_trades += 1
        self.trade_metrics.total_pnl += pnl
        self.trade_metrics.total_fees += fees

        if pnl > 0:
            self.trade_metrics.winning_trades += 1
            self.trades_win_total += 1
        else:
            self.trade_metrics.losing_trades += 1
            self.trades_loss_total += 1

        # Update averages
        self.trade_metrics.avg_trade_duration_minutes = (
            self.trade_metrics.avg_trade_duration_minutes
            * (self.trade_metrics.total_trades - 1)
            + duration_minutes
        ) / self.trade_metrics.total_trades

        self.trade_metrics.max_position_size = max(
            self.trade_metrics.max_position_size, position_size
        )

    def record_drawdown(self, drawdown: float) -> None:
        """Record maximum drawdown.

        Args:
            drawdown: Current drawdown percentage
        """
        self.trade_metrics.max_drawdown = max(self.trade_metrics.max_drawdown, drawdown)

    def record_custom_metric(self, name: str, value: Any) -> None:
        """Record custom metric.

        Args:
            name: Metric name
            value: Metric value
        """
        self.custom_metrics[name] = value

    def increment_liquidity_pools_created(self) -> None:
        """Increment liquidity pools created counter."""
        self.liquidity_pools_created_total += 1

    def increment_signals_emitted(self) -> None:
        """Increment signals emitted counter."""
        self.signals_emitted_total += 1

    def get_realtime_metrics(self) -> dict[str, int]:
        """Get real-time metrics for dashboards.

        Returns:
            Dictionary of real-time metrics
        """
        return {
            "liquidity_pools_created_total": self.liquidity_pools_created_total,
            "signals_emitted_total": self.signals_emitted_total,
            "trades_win_total": self.trades_win_total,
            "trades_loss_total": self.trades_loss_total,
        }

    def increment_counter(self, name: str, increment: int = 1) -> None:
        """Increment a counter metric.

        Args:
            name: Counter name
            increment: Amount to increment by (default 1)
        """
        current = self.custom_metrics.get(name, 0)
        self.custom_metrics[name] = current + increment

    def record_signal_emitted(self) -> None:
        """Record a trading signal emission."""
        self.increment_counter("signals_emitted_total")

    def record_candidate_expired(self) -> None:
        """Record a signal candidate expiration."""
        self.increment_counter("candidates_expired_total")

    def take_memory_snapshot(self) -> MemorySnapshot | None:
        """Take memory snapshot if tracking enabled.

        Returns:
            MemorySnapshot or None if tracking disabled
        """
        if self.memory_tracker:
            return self.memory_tracker.take_snapshot()
        return None

    def get_summary(self) -> dict[str, Any]:
        """Get comprehensive metrics summary.

        Returns:
            Dictionary with all collected metrics
        """
        summary = {
            "execution_time": {
                "start": self.start_time,
                "end": self.end_time,
                "duration_seconds": (
                    (self.end_time - self.start_time).total_seconds()
                    if self.start_time and self.end_time
                    else None
                ),
            },
            "trade_metrics": {
                "total_trades": self.trade_metrics.total_trades,
                "winning_trades": self.trade_metrics.winning_trades,
                "losing_trades": self.trade_metrics.losing_trades,
                "win_rate": (
                    self.trade_metrics.winning_trades / self.trade_metrics.total_trades
                    if self.trade_metrics.total_trades > 0
                    else 0.0
                ),
                "total_pnl": self.trade_metrics.total_pnl,
                "total_fees": self.trade_metrics.total_fees,
                "max_drawdown": self.trade_metrics.max_drawdown,
                "max_position_size": self.trade_metrics.max_position_size,
                "avg_trade_duration_minutes": self.trade_metrics.avg_trade_duration_minutes,
            },
            "custom_metrics": self.custom_metrics,
        }

        # Add latency stats if available
        if self.latency_profiler:
            summary["latency_stats"] = self.latency_profiler.get_all_stats()

        # Add memory stats if available
        if self.memory_tracker:
            summary["memory_stats"] = {
                "peak_usage_mb": self.memory_tracker.get_peak_usage(),
                "snapshot_count": len(self.memory_tracker.snapshots),
            }

        return summary

    def log_summary(self) -> None:
        """Log metrics summary at INFO level."""
        summary = self.get_summary()

        logger.info("=== BACKTEST METRICS SUMMARY ===")

        # Execution time
        exec_time = summary["execution_time"]
        if exec_time["duration_seconds"]:
            logger.info(f"Execution time: {exec_time['duration_seconds']:.2f} seconds")

        # Trade metrics
        trade_stats = summary["trade_metrics"]
        logger.info(f"Total trades: {trade_stats['total_trades']}")
        logger.info(f"Win rate: {trade_stats['win_rate']:.2%}")
        logger.info(f"Total PnL: ${trade_stats['total_pnl']:.2f}")
        logger.info(f"Total fees: ${trade_stats['total_fees']:.2f}")
        logger.info(f"Max drawdown: {trade_stats['max_drawdown']:.2%}")

        # Open positions info (if available)
        if hasattr(self, "_open_positions_info"):
            logger.info(f"Open positions: {self._open_positions_info['count']}")
            logger.info(
                f"Open positions PnL: ${self._open_positions_info['unrealized_pnl']:.2f}"
            )
        else:
            logger.info("Open positions: 0")

        # Latency stats
        if "latency_stats" in summary:
            logger.info("=== LATENCY STATS ===")
            for operation, stats in summary["latency_stats"].items():
                logger.info(
                    f"{operation}: {stats['mean_us']:.0f}μs avg, {stats['p95_us']:.0f}μs p95"
                )

        # Memory stats
        if "memory_stats" in summary:
            logger.info(
                f"Peak memory usage: {summary['memory_stats']['peak_usage_mb']:.1f} MB"
            )

        logger.info("=== END METRICS SUMMARY ===")


# Global metrics collector instance for easy access
_global_metrics: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics


def reset_metrics_collector() -> None:
    """Reset global metrics collector."""
    global _global_metrics
    _global_metrics = None


@contextmanager
def measure_operation(operation: str, **context: Any) -> Iterator[None]:
    """Convenience context manager for measuring operations.

    Args:
        operation: Operation name
        **context: Additional context
    """
    collector = get_metrics_collector()
    with collector.measure_latency(operation, **context):
        yield
