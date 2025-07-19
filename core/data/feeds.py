"""
Data Feeds

Unified data feed system that provides real-time and historical data
to strategies through a consistent interface.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from threading import Event, Thread
from typing import Callable, Dict, List, Optional

from .adapters import DataAdapter
from .models import Candle, MarketData, TimeFrame


class DataFeed(ABC):
    """Abstract base class for data feeds"""

    def __init__(self, adapter: DataAdapter):
        self.adapter = adapter
        self.subscribers = []
        self.is_running = False

    def subscribe(self, callback: Callable[[Candle], None]) -> None:
        """Subscribe to data updates"""
        self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Candle], None]) -> None:
        """Unsubscribe from data updates"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def _notify_subscribers(self, candle: Candle) -> None:
        """Notify all subscribers of new candle"""
        for callback in self.subscribers:
            try:
                callback(candle)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in data feed subscriber: {exc}")

    @abstractmethod
    def start(self) -> None:
        """Start the data feed"""

    @abstractmethod
    def stop(self) -> None:
        """Stop the data feed"""


class LiveDataFeed(DataFeed):
    """Live data feed for real-time trading"""

    def __init__(
        self,
        adapter: DataAdapter,
        symbols: List[str],
        timeframes: List[TimeFrame],
    ):
        super().__init__(adapter)
        self.symbols = symbols
        self.timeframes = timeframes
        self.update_interval = 1.0  # seconds
        self._stop_event = Event()
        self._thread = None
        self.last_candles = {}

    def start(self) -> None:
        """Start live data feed"""
        if self.is_running:
            return

        self.is_running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._run_feed, daemon=True)
        self._thread.start()
        print(f"Live data feed started for {len(self.symbols)} symbols")

    def stop(self) -> None:
        """Stop live data feed"""
        if not self.is_running:
            return

        self.is_running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        print("Live data feed stopped")

    def _run_feed(self) -> None:
        """Run the live data feed loop"""
        while not self._stop_event.is_set():
            try:
                for symbol in self.symbols:
                    for timeframe in self.timeframes:
                        # Get latest candle
                        latest_candle = self.adapter.get_latest_candle(
                            symbol, timeframe
                        )

                        if latest_candle:
                            # Check if this is a new candle
                            key = f"{symbol}_{timeframe.value}"
                            last_timestamp = self.last_candles.get(key)

                            if (
                                not last_timestamp
                                or latest_candle.timestamp > last_timestamp
                            ):
                                self.last_candles[key] = latest_candle.timestamp
                                self._notify_subscribers(latest_candle)

                # Wait before next update
                if not self._stop_event.wait(self.update_interval):
                    continue

            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"Error in live data feed: {exc}")
                time.sleep(5)  # Wait before retrying


class BacktestDataFeed(DataFeed):
    """Data feed for backtesting"""

    def __init__(self, adapter: DataAdapter, market_data: MarketData):
        super().__init__(adapter)
        self.market_data = market_data
        self.current_index = 0
        self.playback_speed = 1.0  # 1.0 = real-time, 0 = instant
        self._stop_event = Event()
        self._thread = None
        self.is_complete = False

    def start(self) -> None:
        """Start backtest data feed"""
        if self.is_running:
            return

        self.is_running = True
        self._stop_event.clear()

        if self.playback_speed == 0:
            # Instant playback - send all candles immediately
            self._instant_playback()
        else:
            # Timed playback
            self._thread = Thread(target=self._timed_playback, daemon=True)
            self._thread.start()

        print(
            f"Backtest data feed started with {len(self.market_data.candles)} candles"
        )

    def stop(self) -> None:
        """Stop backtest data feed"""
        if not self.is_running:
            return

        self.is_running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        print("Backtest data feed stopped")

    def _instant_playback(self) -> None:
        """Send all candles instantly"""
        for candle in self.market_data.candles:
            if self._stop_event.is_set():
                break
            self._notify_subscribers(candle)
            self.current_index += 1

        self.is_complete = True
        self.is_running = False

    def _timed_playback(self) -> None:
        """Send candles with timing simulation"""
        candles = self.market_data.candles

        for i in range(self.current_index, len(candles)):
            if self._stop_event.is_set():
                break

            candle = candles[i]
            self._notify_subscribers(candle)
            self.current_index = i + 1

            # Calculate wait time based on timeframe and playback speed
            if i < len(candles) - 1:
                current_time = candle.timestamp
                next_time = candles[i + 1].timestamp
                time_diff = (next_time - current_time).total_seconds()
                wait_time = time_diff / self.playback_speed

                if self._stop_event.wait(wait_time):
                    break

        self.is_complete = True
        self.is_running = False

    def set_playback_speed(self, speed: float) -> None:
        """Set playback speed (0 = instant, 1.0 = real-time, 2.0 = 2x speed)"""
        self.playback_speed = speed

    def seek_to_timestamp(self, timestamp: datetime) -> None:
        """Seek to a specific timestamp"""
        for i, candle in enumerate(self.market_data.candles):
            if candle.timestamp >= timestamp:
                self.current_index = i
                break

    def get_progress(self) -> float:
        """Get playback progress (0.0 to 1.0)"""
        if not self.market_data.candles:
            return 1.0
        return self.current_index / len(self.market_data.candles)


class MultiSymbolDataFeed(DataFeed):
    """Data feed that handles multiple symbols and timeframes"""

    def __init__(self, adapter: DataAdapter):
        super().__init__(adapter)
        self.feeds = {}
        self.is_live = False

    def add_symbol(self, symbol: str, timeframes: List[TimeFrame]) -> None:
        """Add a symbol with its timeframes"""
        if symbol not in self.feeds:
            self.feeds[symbol] = {"timeframes": timeframes, "last_candles": {}}

    def remove_symbol(self, symbol: str) -> None:
        """Remove a symbol"""
        if symbol in self.feeds:
            del self.feeds[symbol]

    def start_live(self) -> None:
        """Start as live feed"""
        self.is_live = True
        symbols = list(self.feeds.keys())
        timeframes = []

        for symbol_data in self.feeds.values():
            timeframes.extend(symbol_data["timeframes"])

        # Remove duplicates
        timeframes = list(set(timeframes))

        self.live_feed = LiveDataFeed(self.adapter, symbols, timeframes)
        self.live_feed.subscribe(self._on_candle_received)
        self.live_feed.start()

    def start_backtest(self, market_data_collection: Dict[str, MarketData]) -> None:
        """Start as backtest feed with multiple symbols"""
        self.is_live = False

        # Create individual backtest feeds for each symbol
        self.backtest_feeds = {}
        for symbol, market_data in market_data_collection.items():
            if symbol in self.feeds:
                feed = BacktestDataFeed(self.adapter, market_data)
                feed.subscribe(self._on_candle_received)
                self.backtest_feeds[symbol] = feed

        # Start all feeds
        for feed in self.backtest_feeds.values():
            feed.start()

    def _on_candle_received(self, candle: Candle) -> None:
        """Handle incoming candle from underlying feeds"""
        # Update last candle for this symbol/timeframe
        if candle.symbol in self.feeds:
            key = f"{candle.timeframe.value}"
            self.feeds[candle.symbol]["last_candles"][key] = candle

        # Notify our subscribers
        self._notify_subscribers(candle)

    def start(self) -> None:
        """Start the multi-symbol feed"""
        if self.is_live:
            self.start_live()
        # Backtest start is handled separately
        self.is_running = True

    def stop(self) -> None:
        """Stop the multi-symbol feed"""
        if self.is_live and hasattr(self, "live_feed"):
            self.live_feed.stop()
        elif hasattr(self, "backtest_feeds"):
            for feed in self.backtest_feeds.values():
                feed.stop()

        self.is_running = False

    def get_latest_candle(self, symbol: str, timeframe: TimeFrame) -> Optional[Candle]:
        """Get the latest candle for a symbol/timeframe"""
        if symbol in self.feeds:
            key = f"{timeframe.value}"
            return self.feeds[symbol]["last_candles"].get(key)
        return None
