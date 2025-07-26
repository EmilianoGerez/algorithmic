"""Liquidity pool event framework with common ABC for type-safe processing.

See :ref:`design_notebook:Initial Implementation Sprint Plan`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from core.entities import Event


@runtime_checkable
class LiquidityPoolEvent(Event, Protocol):
    """Common protocol for all liquidity pool events.

    Provides type-safe interface for downstream processing with clean
    type switching and standardized fields across all detector types.
    """

    pool_id: str
    side: str  # Event direction: "bullish"/"bearish" or "high"/"low"
    top: float
    bottom: float
    tf: str
    strength: float  # Normalized 0.0-1.0 strength value


@dataclass(frozen=True)
class BasePoolEvent:
    """Base implementation for liquidity pool events."""

    ts: datetime
    pool_id: str
    side: str
    top: float
    bottom: float
    tf: str
    strength: float

    def __post_init__(self) -> None:
        """Validate event data."""
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be 0.0-1.0, got {self.strength}")
        if self.top < self.bottom:
            raise ValueError(f"top ({self.top}) must be >= bottom ({self.bottom})")


class EventClassifier:
    """Utility class for type-safe event processing."""

    @staticmethod
    def is_bullish_event(event: LiquidityPoolEvent) -> bool:
        """Check if event represents bullish liquidity."""
        return event.side in {"bullish", "low"}

    @staticmethod
    def is_bearish_event(event: LiquidityPoolEvent) -> bool:
        """Check if event represents bearish liquidity."""
        return event.side in {"bearish", "high"}

    @staticmethod
    def get_event_type(event: LiquidityPoolEvent) -> str:
        """Get standardized event type string."""
        # Import here to avoid circular imports
        from core.detectors.fvg import FVGEvent
        from core.detectors.pivot import PivotEvent

        if isinstance(event, FVGEvent):
            return f"fvg_{event.side}"
        elif isinstance(event, PivotEvent):
            return f"pivot_{event.side}"
        else:
            return f"unknown_{event.side}"

    @staticmethod
    def get_price_level(event: LiquidityPoolEvent, level_type: str = "center") -> float:
        """Get price level from event.

        Args:
            event: Liquidity pool event.
            level_type: "top", "bottom", "center", or "edge".

        Returns:
            Price level based on event type and level_type.
        """
        if level_type == "top":
            return event.top
        elif level_type == "bottom":
            return event.bottom
        elif level_type == "center":
            return (event.top + event.bottom) / 2
        elif level_type == "edge":
            # Return the "entry" edge based on event direction
            if EventClassifier.is_bullish_event(event):
                return event.bottom  # Enter at bottom of bullish zone
            else:
                return event.top  # Enter at top of bearish zone
        else:
            raise ValueError(f"Unknown level_type: {level_type}")


class EventRegistry:
    """Registry for tracking active liquidity pool events."""

    def __init__(self) -> None:
        self._events: dict[str, LiquidityPoolEvent] = {}
        self._events_by_tf: dict[str, list[str]] = {}

    def add_event(self, event: LiquidityPoolEvent) -> None:
        """Add event to registry."""
        self._events[event.pool_id] = event

        if event.tf not in self._events_by_tf:
            self._events_by_tf[event.tf] = []
        self._events_by_tf[event.tf].append(event.pool_id)

    def get_event(self, pool_id: str) -> LiquidityPoolEvent | None:
        """Get event by pool ID."""
        return self._events.get(pool_id)

    def get_events_by_timeframe(self, tf: str) -> list[LiquidityPoolEvent]:
        """Get all events for a timeframe."""
        pool_ids = self._events_by_tf.get(tf, [])
        return [
            self._events[pool_id] for pool_id in pool_ids if pool_id in self._events
        ]

    def get_all_events(self) -> list[LiquidityPoolEvent]:
        """Get all active events."""
        return list(self._events.values())

    def remove_event(self, pool_id: str) -> bool:
        """Remove event from registry."""
        if pool_id in self._events:
            event = self._events[pool_id]
            del self._events[pool_id]

            if event.tf in self._events_by_tf:
                self._events_by_tf[event.tf] = [
                    pid for pid in self._events_by_tf[event.tf] if pid != pool_id
                ]
            return True
        return False

    def clear_timeframe(self, tf: str) -> int:
        """Clear all events for a timeframe."""
        if tf not in self._events_by_tf:
            return 0

        pool_ids = self._events_by_tf[tf].copy()
        count = 0
        for pool_id in pool_ids:
            if self.remove_event(pool_id):
                count += 1

        return count

    def get_stats(self) -> dict[str, int]:
        """Get registry statistics."""
        stats = {"total_events": len(self._events)}
        for tf, pool_ids in self._events_by_tf.items():
            stats[f"{tf}_events"] = len(pool_ids)
        return stats
