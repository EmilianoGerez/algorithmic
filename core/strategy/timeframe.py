"""Timeframe utilities for multi-timeframe aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple

__all__ = [
    "TimeframeConfig",
    "TimeframePeriod",
    "Timeframe",
    "get_bucket_id",
    "get_bucket_start",
]


class TimeframePeriod(NamedTuple):
    """Timeframe period configuration."""

    minutes: int
    name: str

    @property
    def seconds(self) -> int:
        """Total seconds in this timeframe period."""
        return self.minutes * 60

    def bucket_id(self, timestamp: datetime) -> int:
        """Get bucket ID for timestamp using Unix epoch division.

        This ensures consistent period boundaries without drift.
        Uses UTC epoch to avoid timezone issues.

        Args:
            timestamp: UTC datetime to get bucket for.

        Returns:
            Bucket ID as integer (minutes since epoch / timeframe_minutes).

        Example:
            >>> h1 = TimeframePeriod(60, "H1")
            >>> ts = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
            >>> bucket_id = h1.bucket_id(ts)  # Self-contained and readable
        """
        epoch_minutes = int(timestamp.timestamp()) // 60
        return epoch_minutes // self.minutes

    def bucket_start(self, timestamp: datetime) -> datetime:
        """Get start time of bucket containing the given timestamp.

        Args:
            timestamp: UTC datetime to get bucket start for.

        Returns:
            UTC datetime of bucket start.

        Example:
            >>> h1 = TimeframePeriod(60, "H1")
            >>> ts = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
            >>> start = h1.bucket_start(ts)  # 2024-01-01 10:00:00+00:00
        """
        bucket_id = self.bucket_id(timestamp)
        start_epoch_minutes = bucket_id * self.minutes
        start_timestamp = start_epoch_minutes * 60
        return datetime.fromtimestamp(start_timestamp, tz=UTC)

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.name}({self.minutes} min)"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"TimeframePeriod(minutes={self.minutes}, name='{self.name}')"


# Alias for backward compatibility and cleaner API
Timeframe = TimeframePeriod


class TimeframeConfig:
    """Standard timeframe configurations using Timeframe objects."""

    M1 = Timeframe(1, "M1")
    M5 = Timeframe(5, "M5")
    M15 = Timeframe(15, "M15")
    M30 = Timeframe(30, "M30")
    H1 = Timeframe(60, "H1")
    H2 = Timeframe(120, "H2")
    H4 = Timeframe(240, "H4")
    H6 = Timeframe(360, "H6")
    H12 = Timeframe(720, "H12")
    D1 = Timeframe(1440, "D1")
    W1 = Timeframe(10080, "W1")  # 7 * 24 * 60


def get_bucket_id(timestamp: datetime, tf_minutes: int) -> int:
    """Get bucket ID for timestamp using Unix epoch minute division.

    This ensures consistent period boundaries without drift.

    Args:
        timestamp: UTC timestamp to bucket.
        tf_minutes: Timeframe period in minutes.

    Returns:
        Integer bucket ID for the timeframe period.

    Example:
        >>> dt = datetime(2025, 1, 1, 14, 30)  # 14:30 UTC
        >>> get_bucket_id(dt, 60)  # H1 bucket
        438252  # Example bucket ID
    """
    epoch_minutes = int(timestamp.timestamp()) // 60
    return epoch_minutes // tf_minutes


def get_bucket_start(timestamp: datetime, tf_minutes: int) -> datetime:
    """Get the start timestamp of the bucket containing the given timestamp.

    Args:
        timestamp: UTC timestamp to find bucket start for.
        tf_minutes: Timeframe period in minutes.

    Returns:
        Start timestamp of the bucket period.

    Example:
        >>> dt = datetime(2025, 1, 1, 14, 35)  # 14:35 UTC
        >>> get_bucket_start(dt, 60)  # H1 bucket start
        datetime(2025, 1, 1, 14, 0)  # 14:00 UTC
    """
    bucket_id = get_bucket_id(timestamp, tf_minutes)
    bucket_start_minutes = bucket_id * tf_minutes
    return datetime.fromtimestamp(bucket_start_minutes * 60, tz=UTC)


def format_timeframe_name(tf_minutes: int) -> str:
    """Format timeframe minutes into standard name.

    Args:
        tf_minutes: Timeframe period in minutes.

    Returns:
        Standard timeframe name (e.g., "H1", "H4", "D1").

    Example:
        >>> format_timeframe_name(60)
        "H1"
        >>> format_timeframe_name(1440)
        "D1"
    """
    if tf_minutes < 60:
        return f"M{tf_minutes}"
    elif tf_minutes < 1440:
        hours = tf_minutes // 60
        return f"H{hours}"
    elif tf_minutes < 10080:
        days = tf_minutes // 1440
        return f"D{days}"
    else:
        weeks = tf_minutes // 10080
        return f"W{weeks}"
