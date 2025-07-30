"""
High-performance TTL wheel implementation for O(1) pool expiry management.

Implements a hierarchical timing wheel for efficient batch expiry of liquidity pools.
Supports deterministic time advancement for testing and handles out-of-order events.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from core.clock import get_clock

# TTL Wheel bucket size constants - tweak these for performance/memory trade-offs
SEC_BUCKETS = 60  # 0-59 seconds wheel
MIN_BUCKETS = 60  # 0-59 minutes wheel
HOUR_BUCKETS = 24  # 0-23 hours wheel
DAY_BUCKETS = 7  # 0-6 days wheel (weekly cycle)

__all__ = [
    "TimerWheel",
    "ScheduledExpiry",
    "WheelConfig",
    "SEC_BUCKETS",
    "MIN_BUCKETS",
    "HOUR_BUCKETS",
    "DAY_BUCKETS",
]


@dataclass(slots=True)
class ScheduledExpiry:
    """Represents a scheduled expiry event in the timing wheel."""

    pool_id: str
    expires_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate expiry scheduling."""
        # Only validate if both times are in the same time context
        # Allow created_at in past if expires_at is reasonable relative to current time
        pass  # Validation moved to schedule() method for better context


@dataclass
class WheelConfig:
    """Configuration for the TTL timing wheel."""

    # Wheel granularity levels (4-level hierarchical design)
    second_slots: int = SEC_BUCKETS  # 0-59 seconds
    minute_slots: int = MIN_BUCKETS  # 0-59 minutes
    hour_slots: int = HOUR_BUCKETS  # 0-23 hours
    day_slots: int = DAY_BUCKETS  # 0-6 days (weekly cycle)

    # Performance tuning
    max_items_per_slot: int = 1000  # Warning threshold for slot size
    enable_metrics: bool = True  # Emit performance metrics

    def total_capacity_seconds(self) -> int:
        """Calculate maximum TTL capacity in seconds."""
        return (
            self.second_slots
            + (self.minute_slots * 60)
            + (self.hour_slots * 3600)
            + (self.day_slots * 86400)
        )


class TimerWheel:
    """
    Hierarchical timing wheel for O(1) pool expiry scheduling.

    Uses a 4-level wheel design:
    - Level 0: 60 slots for seconds (0-59s)
    - Level 1: 60 slots for minutes (1-60m)
    - Level 2: 24 slots for hours (1-24h)
    - Level 3: 7 slots for days (1-7d)

    Supports:
    - O(1) insertion and expiry checking
    - Deterministic time advancement for testing
    - Out-of-order event handling
    - Batch expiry processing
    """

    def __init__(self, config: WheelConfig | None = None):
        """Initialize the timing wheel with configuration."""
        self.config = config or WheelConfig()
        # Use global clock for consistent time management
        self.current_time = get_clock().now()

        # Initialize wheel levels
        self._wheels: list[list[list[ScheduledExpiry]]] = [
            [[] for _ in range(self.config.second_slots)],  # Seconds wheel
            [[] for _ in range(self.config.minute_slots)],  # Minutes wheel
            [[] for _ in range(self.config.hour_slots)],  # Hours wheel
            [[] for _ in range(self.config.day_slots)],  # Days wheel
        ]

        # Fast lookup for cancellation/updates
        self._pool_to_expiry: dict[str, ScheduledExpiry] = {}

        # Metrics tracking
        self._metrics = {
            "total_scheduled": 0,
            "total_expired": 0,
            "max_slot_size": 0,
            "wheel_advances": 0,
        }

    def schedule(
        self, pool_id: str, expires_at: datetime, created_at: datetime | None = None
    ) -> bool:
        """
        Schedule a pool for expiry.

        Args:
            pool_id: Unique pool identifier
            expires_at: When the pool should expire
            created_at: When the pool was created (defaults to current time)

        Returns:
            True if scheduled successfully, False if already scheduled
        """
        if pool_id in self._pool_to_expiry:
            return False  # Already scheduled

        created_at = created_at or get_clock().now()

        # Handle out-of-order events (expiry in the past or at current time)
        if expires_at <= self.current_time:
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                f"Expiry in past - skip pool {pool_id}: {expires_at} <= {self.current_time}"
            )
            return False

        # Only validate expiry vs creation if created_at is in the past
        if created_at < self.current_time and expires_at < created_at:
            raise ValueError(
                f"Expiry time {expires_at} cannot be before creation {created_at}"
            )

        expiry = ScheduledExpiry(pool_id, expires_at, created_at)

        # Calculate time delta and determine wheel level
        delta_seconds = int((expires_at - self.current_time).total_seconds())
        wheel_level, slot_index = self._calculate_wheel_position(delta_seconds)

        # Add to appropriate wheel
        self._wheels[wheel_level][slot_index].append(expiry)
        self._pool_to_expiry[pool_id] = expiry

        # Update metrics
        self._metrics["total_scheduled"] += 1
        slot_size = len(self._wheels[wheel_level][slot_index])
        self._metrics["max_slot_size"] = max(self._metrics["max_slot_size"], slot_size)

        # Debug logging
        import logging

        logger = logging.getLogger(__name__)
        ttl_delta = expires_at - created_at
        logger.debug(
            f"Pool {pool_id} TTL {ttl_delta} scheduled in bucket level={wheel_level} slot={slot_index}"
        )

        # Warning for slot size
        if slot_size > self.config.max_items_per_slot:
            logger.warning(f"Slot {wheel_level}:{slot_index} has {slot_size} items")

        return True

    def cancel(self, pool_id: str) -> bool:
        """
        Cancel a scheduled expiry.

        Args:
            pool_id: Pool to cancel

        Returns:
            True if cancelled, False if not found
        """
        if pool_id not in self._pool_to_expiry:
            return False

        expiry = self._pool_to_expiry.pop(pool_id)

        # Find and remove from wheel (expensive O(n) operation)
        delta_seconds = int((expiry.expires_at - self.current_time).total_seconds())
        if delta_seconds > 0:  # Only search if not already expired
            wheel_level, slot_index = self._calculate_wheel_position(delta_seconds)
            slot = self._wheels[wheel_level][slot_index]
            with suppress(ValueError):
                slot.remove(expiry)  # Already removed or expired

        return True

    def tick(self, new_time: datetime) -> list[ScheduledExpiry]:
        """
        Advance the wheel to a new time and return expired items.

        Args:
            new_time: New current time

        Returns:
            List of expired pool items
        """
        if new_time < self.current_time:
            raise ValueError(
                f"Time cannot go backwards: {new_time} < {self.current_time}"
            )

        expired_items: list[ScheduledExpiry] = []

        while self.current_time < new_time:
            # Advance by one second
            self.current_time += timedelta(seconds=1)
            expired_items.extend(self._advance_second())
            self._metrics["wheel_advances"] += 1

        # Update metrics
        self._metrics["total_expired"] += len(expired_items)

        # Clean up expired items from lookup
        for item in expired_items:
            self._pool_to_expiry.pop(item.pool_id, None)

        return expired_items

    def expire_due(self, now: datetime) -> list[ScheduledExpiry]:
        """
        Get all items that should be expired by the given time.

        This is a non-advancing check - useful for querying without changing state.

        Args:
            now: Time to check against

        Returns:
            List of items that should be expired
        """
        expired: list[ScheduledExpiry] = []

        for expiry in self._pool_to_expiry.values():
            if expiry.expires_at <= now:
                expired.append(expiry)

        return expired

    def size(self) -> int:
        """Return total number of scheduled items."""
        return len(self._pool_to_expiry)

    def get_metrics(self) -> dict[str, Any]:
        """Return performance metrics."""
        return {
            **self._metrics,
            "current_size": self.size(),
            "current_time": self.current_time.isoformat(),
        }

    def _calculate_wheel_position(self, delta_seconds: int) -> tuple[int, int]:
        """
        Calculate which wheel level and slot for a given time delta.

        Args:
            delta_seconds: Seconds from current time

        Returns:
            Tuple of (wheel_level, slot_index)
        """
        return self._calculate_wheel_position_from_time(
            delta_seconds, self.current_time
        )

    def _calculate_wheel_position_from_time(
        self, delta_seconds: int, reference_time: datetime
    ) -> tuple[int, int]:
        """
        Calculate which wheel level and slot for a given time delta from a specific reference time.

        Args:
            delta_seconds: Seconds from reference time
            reference_time: Time to calculate from

        Returns:
            Tuple of (wheel_level, slot_index)
        """
        if delta_seconds < self.config.second_slots:
            # Seconds wheel (0-59s)
            current_second = reference_time.second
            slot_index = (current_second + delta_seconds) % self.config.second_slots
            return (0, slot_index)
        elif delta_seconds < self.config.minute_slots * 60:
            # Minutes wheel (1-60m)
            delta_minutes = delta_seconds // 60
            current_minute = reference_time.minute
            slot_index = (current_minute + delta_minutes) % self.config.minute_slots
            return (1, slot_index)
        elif delta_seconds < self.config.hour_slots * 3600:
            # Hours wheel (1-24h)
            delta_hours = delta_seconds // 3600
            current_hour = reference_time.hour
            slot_index = (current_hour + delta_hours) % self.config.hour_slots
            return (2, slot_index)
        else:
            # Days wheel (1-7d)
            delta_days = delta_seconds // 86400
            current_day = reference_time.weekday()
            slot_index = (current_day + delta_days) % self.config.day_slots
            return (3, slot_index)

    def _advance_second(self) -> list[ScheduledExpiry]:
        """Advance the seconds wheel by one second and return expired items."""
        current_slot = self.current_time.second
        expired_items = self._wheels[0][current_slot].copy()
        self._wheels[0][current_slot].clear()

        # Handle wheel rollovers AFTER checking minute/hour/day boundaries
        # We need to use the NEXT time for cascading calculations
        next_time = self.current_time + timedelta(seconds=1)

        if current_slot == 59:  # About to wrap to 0, so minute will change
            next_minute = next_time.minute
            self._cascade_wheel(1, next_minute, next_time)

            if next_minute == 0:  # Hour rollover
                next_hour = next_time.hour
                self._cascade_wheel(2, next_hour, next_time)

                if next_hour == 0:  # Day rollover
                    next_day = next_time.weekday()
                    self._cascade_wheel(3, next_day, next_time)

        return expired_items

    def _cascade_wheel(
        self, wheel_level: int, slot_index: int, reference_time: datetime
    ) -> None:
        """Move items from higher-level wheel to lower-level wheels."""
        items_to_cascade = self._wheels[wheel_level][slot_index].copy()
        self._wheels[wheel_level][slot_index].clear()

        for item in items_to_cascade:
            # Recalculate position using the reference time (next time)
            delta_seconds = int((item.expires_at - reference_time).total_seconds())

            if delta_seconds > 0:
                new_wheel_level, new_slot_index = (
                    self._calculate_wheel_position_from_time(
                        delta_seconds, reference_time
                    )
                )
                self._wheels[new_wheel_level][new_slot_index].append(item)
            else:
                # If delta_seconds <= 0, the item should expire immediately
                # Add it to the current second's slot so it will be picked up
                current_second_slot = reference_time.second
                self._wheels[0][current_second_slot].append(item)
