"""
Replay engine for deterministic backtesting with event-driven architecture.

This module provides the core replay functionality that processes historical
market data in a deterministic, event-driven manner. Supports multiple
replay modes including real-time simulation and fast replay.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Protocol

from core.entities import Candle
from services.metrics import MetricsCollector, measure_operation

logger = logging.getLogger(__name__)


class ReplayMode(Enum):
    """Replay execution modes."""

    FAST = "fast"  # Process as fast as possible
    REALTIME = "realtime"  # Simulate real-time with delays
    STEPPED = "stepped"  # Manual step-by-step control


class EventType(Enum):
    """Types of replay events."""

    CANDLE = "candle"
    TRADE = "trade"
    ORDERBOOK = "orderbook"
    NEWS = "news"
    SYSTEM = "system"


class ReplayEvent:
    """Single event in the replay timeline."""

    def __init__(self, timestamp: datetime, event_type: EventType, data: Any):
        """Initialize replay event.

        Args:
            timestamp: Event timestamp
            event_type: Type of event
            data: Event payload
        """
        self.timestamp = timestamp
        self.event_type = event_type
        self.data = data

    def __lt__(self, other: ReplayEvent) -> bool:
        """Enable sorting by timestamp."""
        return self.timestamp < other.timestamp

    def __repr__(self) -> str:
        return f"ReplayEvent({self.timestamp}, {self.event_type}, {type(self.data).__name__})"


class EventHandler(Protocol):
    """Protocol for event handlers in the replay engine."""

    def handle_event(self, event: ReplayEvent) -> None:
        """Handle a replay event.

        Args:
            event: Event to handle
        """
        ...


class ReplayEngine:
    """Event-driven replay engine for backtesting."""

    def __init__(
        self,
        mode: ReplayMode = ReplayMode.FAST,
        metrics_collector: MetricsCollector | None = None,
    ):
        """Initialize replay engine.

        Args:
            mode: Replay mode (fast, realtime, stepped)
            metrics_collector: Optional metrics collector
        """
        self.mode = mode
        self.metrics = metrics_collector
        self.handlers: list[EventHandler] = []
        self.events: list[ReplayEvent] = []
        self.current_time: datetime | None = None
        self.is_running = False
        self.step_mode_paused = mode == ReplayMode.STEPPED

        # Replay state
        self.total_events = 0
        self.processed_events = 0
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

        logger.info(f"Replay engine initialized in {mode.value} mode")

    def add_handler(self, handler: EventHandler) -> None:
        """Add event handler to the engine.

        Args:
            handler: Event handler implementing EventHandler protocol
        """
        self.handlers.append(handler)
        logger.debug(f"Added event handler: {type(handler).__name__}")

    def add_candle_stream(self, candle_stream: Iterator[Candle]) -> None:
        """Add candle stream as events to the replay timeline.

        Args:
            candle_stream: Iterator of Candle objects
        """
        candle_count = 0

        with measure_operation("load_candle_stream"):
            for candle in candle_stream:
                event = ReplayEvent(
                    timestamp=candle.ts, event_type=EventType.CANDLE, data=candle
                )
                self.events.append(event)
                candle_count += 1

        logger.info(f"Added {candle_count} candle events to replay timeline")

    def add_event(self, timestamp: datetime, event_type: EventType, data: Any) -> None:
        """Add custom event to the replay timeline.

        Args:
            timestamp: Event timestamp
            event_type: Type of event
            data: Event data
        """
        event = ReplayEvent(timestamp, event_type, data)
        self.events.append(event)

    def prepare_replay(self) -> None:
        """Prepare the replay by sorting events and setting bounds."""
        if not self.events:
            raise ValueError("No events loaded for replay")

        with measure_operation("prepare_replay"):
            # Sort events by timestamp for deterministic ordering
            self.events.sort()

            self.total_events = len(self.events)
            self.start_time = self.events[0].timestamp
            self.end_time = self.events[-1].timestamp

            logger.info(
                f"Prepared replay: {self.total_events} events from {self.start_time} to {self.end_time}"
            )

    def run(self) -> None:
        """Run the complete replay."""
        if not self.events:
            raise ValueError("No events to replay. Call prepare_replay() first.")

        logger.info("Starting replay execution")

        if self.metrics:
            self.metrics.start_collection()

        self.is_running = True
        self.processed_events = 0

        try:
            if self.mode == ReplayMode.STEPPED:
                self._run_stepped_mode()
            elif self.mode == ReplayMode.REALTIME:
                self._run_realtime_mode()
            else:  # FAST mode
                self._run_fast_mode()

        except Exception as e:
            logger.error(f"Replay execution failed: {e}")
            raise
        finally:
            self.is_running = False
            if self.metrics:
                self.metrics.stop_collection()

            logger.info(
                f"Replay completed: {self.processed_events}/{self.total_events} events processed"
            )

    def _run_fast_mode(self) -> None:
        """Run replay in fast mode (process events as quickly as possible)."""
        logger.info("Running replay in FAST mode")

        for event in self.events:
            if not self.is_running:
                break

            self._process_event(event)
            self.processed_events += 1

            # Log progress periodically
            if self.processed_events % 10000 == 0:
                progress = (self.processed_events / self.total_events) * 100
                logger.info(
                    f"Replay progress: {progress:.1f}% ({self.processed_events}/{self.total_events})"
                )

    def _run_realtime_mode(self) -> None:
        """Run replay in real-time mode with appropriate delays."""
        import time

        logger.info("Running replay in REALTIME mode")

        real_start_time = time.time()
        replay_start_time = self.events[0].timestamp

        for event in self.events:
            if not self.is_running:
                break

            # Calculate time delay to maintain real-time pace
            elapsed_real = time.time() - real_start_time
            elapsed_replay = (event.timestamp - replay_start_time).total_seconds()

            if elapsed_replay > elapsed_real:
                sleep_time = elapsed_replay - elapsed_real
                if sleep_time > 0:
                    time.sleep(sleep_time)

            self._process_event(event)
            self.processed_events += 1

    def _run_stepped_mode(self) -> None:
        """Run replay in stepped mode (manual control)."""
        logger.info("Running replay in STEPPED mode - call step() to advance")

        while self.processed_events < self.total_events and self.is_running:
            if self.step_mode_paused:
                time.sleep(0.01)  # Small sleep to prevent busy waiting
                continue

            event = self.events[self.processed_events]
            self._process_event(event)
            self.processed_events += 1
            self.step_mode_paused = True  # Pause after each event

    def step(self) -> bool:
        """Advance one step in stepped mode.

        Returns:
            True if there are more events, False if replay is complete
        """
        if self.mode != ReplayMode.STEPPED:
            raise ValueError("step() only available in STEPPED mode")

        if self.processed_events >= self.total_events:
            return False

        self.step_mode_paused = False
        return True

    def _process_event(self, event: ReplayEvent) -> None:
        """Process a single event by dispatching to all handlers.

        Args:
            event: Event to process
        """
        self.current_time = event.timestamp

        with measure_operation("process_event", event_type=event.event_type.value):
            for handler in self.handlers:
                try:
                    with measure_operation(
                        f"handler_{type(handler).__name__}",
                        event_type=event.event_type.value,
                    ):
                        handler.handle_event(event)
                except Exception as e:
                    logger.error(
                        f"Handler {type(handler).__name__} failed on event {event}: {e}"
                    )
                    # Continue with other handlers

    def stop(self) -> None:
        """Stop the replay execution."""
        logger.info("Stopping replay execution")
        self.is_running = False

    def get_progress(self) -> float:
        """Get replay progress as percentage.

        Returns:
            Progress percentage (0.0 to 100.0)
        """
        if self.total_events == 0:
            return 0.0
        return (self.processed_events / self.total_events) * 100.0

    def get_status(self) -> dict[str, Any]:
        """Get detailed replay status.

        Returns:
            Dictionary with replay status information
        """
        return {
            "mode": self.mode.value,
            "is_running": self.is_running,
            "total_events": self.total_events,
            "processed_events": self.processed_events,
            "progress_percent": self.get_progress(),
            "current_time": self.current_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "step_mode_paused": self.step_mode_paused
            if self.mode == ReplayMode.STEPPED
            else None,
        }


class StrategyEventHandler:
    """Event handler that bridges replay events to strategy execution."""

    def __init__(self, strategy: Any, broker: Any):
        """Initialize strategy event handler.

        Args:
            strategy: Strategy instance
            broker: Broker instance for order execution
        """
        self.strategy = strategy
        self.broker = broker
        self.logger = logging.getLogger(self.__class__.__name__)

    def handle_event(self, event: ReplayEvent) -> None:
        """Handle replay event by forwarding to strategy.

        Args:
            event: Replay event to handle
        """
        if event.event_type == EventType.CANDLE:
            candle = event.data

            # Update broker with new market data
            self.broker.update_market_data(candle)

            # Let strategy process the candle
            with measure_operation("strategy_on_candle"):
                self.strategy.on_candle(candle)

        elif event.event_type == EventType.TRADE:
            # Handle trade events if needed
            pass

        elif event.event_type == EventType.SYSTEM:
            # Handle system events (start/stop/checkpoint)
            pass


class MetricsEventHandler:
    """Event handler for collecting replay metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        """Initialize metrics event handler.

        Args:
            metrics_collector: Metrics collector instance
        """
        self.metrics = metrics_collector
        self.candle_count = 0
        self.last_snapshot_time: datetime | None = None
        self.snapshot_interval = timedelta(minutes=5)  # Take snapshots every 5 minutes

    def handle_event(self, event: ReplayEvent) -> None:
        """Handle event for metrics collection.

        Args:
            event: Replay event
        """
        if event.event_type == EventType.CANDLE:
            self.candle_count += 1

            # Take periodic memory snapshots
            if (
                self.last_snapshot_time is None
                or event.timestamp >= self.last_snapshot_time + self.snapshot_interval
            ):
                self.metrics.take_memory_snapshot()
                self.last_snapshot_time = event.timestamp

            # Record custom metrics
            if self.candle_count % 1000 == 0:
                self.metrics.record_custom_metric(
                    "candles_processed", self.candle_count
                )


def create_backtest_replay(
    candle_stream: Iterator[Candle],
    strategy: Any,
    broker: Any,
    mode: ReplayMode = ReplayMode.FAST,
    metrics_collector: MetricsCollector | None = None,
) -> ReplayEngine:
    """Factory function to create a complete backtest replay setup.

    Args:
        candle_stream: Stream of market data candles
        strategy: Strategy instance
        broker: Broker instance
        mode: Replay mode
        metrics_collector: Optional metrics collector

    Returns:
        Configured ReplayEngine ready to run
    """
    # Create replay engine
    engine = ReplayEngine(mode=mode, metrics_collector=metrics_collector)

    # Add candle data
    engine.add_candle_stream(candle_stream)

    # Add strategy handler
    strategy_handler = StrategyEventHandler(strategy, broker)
    engine.add_handler(strategy_handler)

    # Add metrics handler if collector provided
    if metrics_collector:
        metrics_handler = MetricsEventHandler(metrics_collector)
        engine.add_handler(metrics_handler)

    # Prepare for execution
    engine.prepare_replay()

    logger.info("Backtest replay engine created and ready to run")
    return engine
