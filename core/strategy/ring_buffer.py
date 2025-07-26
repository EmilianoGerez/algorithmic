"""Efficient ring buffer implementation for time-series data."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from typing import Generic, TypeVar

from core.entities import Candle

__all__ = ["RingBuffer", "CandleBuffer"]

T = TypeVar("T")


class RingBuffer(Generic[T]):
    """High-performance ring buffer with fixed maximum size.

    Uses collections.deque for O(1) insertions and automatic size management.
    Perfect for maintaining recent history without memory leaks.

    Args:
        maxsize: Maximum number of items to store. Oldest items are
                automatically removed when capacity is exceeded.

    Example:
        >>> buffer = RingBuffer[int](maxsize=3)
        >>> buffer.append(1)
        >>> buffer.append(2)
        >>> buffer.append(3)
        >>> buffer.append(4)  # 1 is automatically removed
        >>> list(buffer)
        [2, 3, 4]
    """

    def __init__(self, maxsize: int):
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self._buffer: deque[T] = deque(maxlen=maxsize)
        self._maxsize = maxsize

    def append(self, item: T) -> None:
        """Add item to the buffer. Oldest item removed if at capacity."""
        self._buffer.append(item)

    def extend(self, items: list[T]) -> None:
        """Add multiple items to the buffer."""
        self._buffer.extend(items)

    def clear(self) -> None:
        """Remove all items from the buffer."""
        self._buffer.clear()

    def __len__(self) -> int:
        """Number of items currently in buffer."""
        return len(self._buffer)

    def __iter__(self) -> Iterator[T]:
        """Iterate over items from oldest to newest."""
        return iter(self._buffer)

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"RingBuffer(size={len(self)}/{self._maxsize}, items={len(self._buffer)})"
        )

    def __getitem__(self, index: int) -> T:
        """Get item by index (0 = oldest, -1 = newest)."""
        return self._buffer[index]

    def __bool__(self) -> bool:
        """True if buffer contains any items."""
        return len(self._buffer) > 0

    @property
    def maxsize(self) -> int:
        """Maximum capacity of the buffer."""
        return self._maxsize

    @property
    def is_full(self) -> bool:
        """True if buffer is at maximum capacity."""
        return len(self._buffer) == self._maxsize

    @property
    def newest(self) -> T:
        """Get the most recently added item.

        Raises:
            IndexError: If buffer is empty.
        """
        if not self._buffer:
            raise IndexError("Buffer is empty")
        return self._buffer[-1]

    @property
    def oldest(self) -> T:
        """Get the oldest item in buffer.

        Raises:
            IndexError: If buffer is empty.
        """
        if not self._buffer:
            raise IndexError("Buffer is empty")
        return self._buffer[0]

    def to_list(self) -> list[T]:
        """Convert buffer contents to list (oldest to newest)."""
        return list(self._buffer)


class CandleBuffer(RingBuffer[Candle]):
    """Specialized ring buffer for OHLCV candle data.

    Provides additional methods for financial time-series analysis.

    Example:
        >>> buffer = CandleBuffer(maxsize=100)
        >>> buffer.append(candle1)
        >>> buffer.append(candle2)
        >>> total_vol = buffer.total_volume()
        >>> high_price = buffer.max_high()
    """

    def total_volume(self) -> float:
        """Calculate total volume across all candles in buffer.

        Returns:
            Sum of volume for all candles, 0.0 if empty.
        """
        return sum(candle.volume for candle in self._buffer)

    def max_high(self) -> float:
        """Get the highest high price across all candles.

        Returns:
            Maximum high price.

        Raises:
            ValueError: If buffer is empty.
        """
        if not self._buffer:
            raise ValueError("Cannot get max_high from empty buffer")
        return max(candle.high for candle in self._buffer)

    def min_low(self) -> float:
        """Get the lowest low price across all candles.

        Returns:
            Minimum low price.

        Raises:
            ValueError: If buffer is empty.
        """
        if not self._buffer:
            raise ValueError("Cannot get min_low from empty buffer")
        return min(candle.low for candle in self._buffer)

    def get_ohlcv(self) -> tuple[float, float, float, float, float]:
        """Calculate OHLCV from all candles in buffer.

        Returns:
            Tuple of (open, high, low, close, volume) aggregated across
            all candles in the buffer.

        Raises:
            ValueError: If buffer is empty.
        """
        if not self._buffer:
            raise ValueError("Cannot calculate OHLCV from empty buffer")

        candles = list(self._buffer)

        # OHLCV aggregation rules:
        # Open: First candle's open
        # High: Maximum high across all candles
        # Low: Minimum low across all candles
        # Close: Last candle's close
        # Volume: Sum of all volumes

        open_price = candles[0].open
        high_price = max(candle.high for candle in candles)
        low_price = min(candle.low for candle in candles)
        close_price = candles[-1].close
        total_volume = sum(candle.volume for candle in candles)

        return open_price, high_price, low_price, close_price, total_volume
