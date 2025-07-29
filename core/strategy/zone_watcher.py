"""
Zone watcher for monitoring price interactions with liquidity pools and HLZs.

This module implements the ZoneWatcher that subscribes to pool/HLZ events,
monitors price movements, and spawns SignalCandidate instances when zones
are entered. Designed for stateless operation with fast lookups.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.entities import Candle

from .pool_models import (
    HLZCreatedEvent,
    HLZExpiredEvent,
    HLZUpdatedEvent,
    PoolCreatedEvent,
    PoolExpiredEvent,
    PoolTouchedEvent,
)
from .signal_candidate import CandidateConfig, SignalCandidateFSM
from .signal_models import (
    SignalDirection,
    ZoneEnteredEvent,
    ZoneType,
)

__all__ = [
    "ZoneWatcherConfig",
    "ZoneMeta",
    "ZoneWatcher",
]


@dataclass(slots=True, frozen=True)
class ZoneWatcherConfig:
    """Configuration for zone watcher."""

    price_tolerance: float = 0.0  # Price tolerance in points for zone entry
    confirm_closure: bool = False  # Wait for bar close to confirm entry
    min_strength: float = 1.0  # Minimum zone strength to track
    max_active_zones: int = 1000  # Maximum zones to track simultaneously


@dataclass(slots=True, frozen=False)  # Changed to mutable for state tracking
class ZoneMeta:
    """Metadata for tracking active zones."""

    zone_id: str
    zone_type: ZoneType
    top: float
    bottom: float
    strength: float
    side: str  # "bullish", "bearish", "neutral"
    timeframe: str  # For pools, empty for HLZs
    created_at: datetime
    last_price_check: float | None = None  # Last price that was checked
    entry_triggered: bool = False  # Track if zone entry has been triggered

logger = logging.getLogger(__name__)


class ZoneWatcher:
    """
    Zone watcher for monitoring price interactions with liquidity zones.

    Subscribes to pool and HLZ lifecycle events, tracks active zones,
    and spawns signal candidates when price enters zones. Designed for
    high-frequency operation with minimal state.
    """

    def __init__(
        self,
        config: ZoneWatcherConfig | None = None,
        candidate_config: CandidateConfig | None = None,
    ):
        """Initialize zone watcher."""
        self.config = config or ZoneWatcherConfig()
        self.candidate_fsm = SignalCandidateFSM(candidate_config or CandidateConfig())

        # Fast lookup for active zones (stateless design)
        self._active_zones: dict[str, ZoneMeta] = {}

        # Track active signal candidates for FSM processing
        self.active_candidates: list[Any] = []  # List of SignalCandidate instances

        # Statistics
        self._stats = {
            "zones_tracked": 0,
            "zone_entries": 0,
            "candidates_spawned": 0,
            "zones_expired": 0,
        }

    def on_price_update(self, candle: Candle) -> list[ZoneEnteredEvent]:
        """
        Process price update and detect zone entries.

        Args:
            candle: Current price candle

        Returns:
            List of zone entry events
        """
        events: list[ZoneEnteredEvent] = []

        # Check each active zone for price entry
        for zone_meta in list(self._active_zones.values()):
            if self._is_price_in_zone(candle.close, zone_meta):
                # Only trigger if zone entry hasn't been triggered yet
                if not zone_meta.entry_triggered:
                    # Price entered zone - create entry event
                    event = ZoneEnteredEvent(
                        zone_id=zone_meta.zone_id,
                        zone_type=zone_meta.zone_type,
                        entry_price=candle.close,
                        timestamp=candle.ts,
                        timeframe=zone_meta.timeframe,
                        strength=zone_meta.strength,
                        side=zone_meta.side,
                    )
                    events.append(event)
                    self._stats["zone_entries"] += 1

                    # Mark zone as entered
                    zone_meta.entry_triggered = True
            else:
                # Price outside zone - reset entry trigger for potential re-entry
                zone_meta.entry_triggered = False

        return events

    def on_pool_event(
        self, event: PoolCreatedEvent | PoolTouchedEvent | PoolExpiredEvent
    ) -> None:
        """Handle pool lifecycle events."""
        match event:
            case PoolCreatedEvent():
                self._add_pool_zone(event)
            case PoolTouchedEvent():
                # Pool touched - could remove from tracking or keep for overlap
                pass
            case PoolExpiredEvent():
                self._remove_zone(event.pool_id)

    def on_hlz_event(
        self, event: HLZCreatedEvent | HLZUpdatedEvent | HLZExpiredEvent
    ) -> None:
        """Handle HLZ lifecycle events."""
        match event:
            case HLZCreatedEvent():
                self._add_hlz_zone(event)
            case HLZUpdatedEvent():
                self._update_hlz_zone(event)
            case HLZExpiredEvent():
                self._remove_zone(event.hlz_id)

    def spawn_candidate(
        self, zone_entry: ZoneEnteredEvent, timestamp: datetime
    ) -> Any:  # Returns SignalCandidate but avoiding circular import
        """
        Spawn signal candidate from zone entry event.

        Args:
            zone_entry: Zone entry event
            timestamp: Current timestamp

        Returns:
            New SignalCandidate instance
        """
        # Determine signal direction based on zone side
        direction = self._infer_direction(zone_entry.side)

        candidate = self.candidate_fsm.create_candidate(
            zone_id=zone_entry.zone_id,
            zone_type=zone_entry.zone_type.value,
            direction=direction,
            entry_price=zone_entry.entry_price,
            strength=zone_entry.strength,
            timestamp=timestamp,
        )

        # Track active candidate for FSM processing
        self.active_candidates.append(candidate)
        self._stats["candidates_spawned"] += 1
        return candidate

    def get_active_zones(self) -> dict[str, ZoneMeta]:
        """Get currently tracked zones."""
        return self._active_zones.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get watcher statistics."""
        return {
            **self._stats,
            "active_zones": len(self._active_zones),
        }

    def _add_pool_zone(self, event: PoolCreatedEvent) -> None:
        """Add pool to zone tracking."""
        pool = event.pool

        logger.info(f"Zone watcher: Adding pool {pool.pool_id} with strength {pool.strength} (min_threshold: {self.config.min_strength})")

        # Skip if strength below threshold
        if pool.strength < self.config.min_strength:
            logger.warning(f"Zone watcher: Pool {pool.pool_id} strength {pool.strength} below threshold {self.config.min_strength}, skipping")
            return

        # Skip if already tracking max zones
        if len(self._active_zones) >= self.config.max_active_zones:
            logger.warning(f"Zone watcher: Already tracking max zones ({self.config.max_active_zones}), skipping pool {pool.pool_id}")
            return

        zone_meta = ZoneMeta(
            zone_id=pool.pool_id,
            zone_type=ZoneType.POOL,
            top=pool.top,
            bottom=pool.bottom,
            strength=pool.strength,
            side=self._infer_pool_side(pool),
            timeframe=pool.timeframe,
            created_at=event.timestamp,
        )

        self._active_zones[pool.pool_id] = zone_meta
        self._stats["zones_tracked"] += 1
        logger.info(f"Zone watcher: Successfully added pool {pool.pool_id} to tracking. Total zones: {len(self._active_zones)}")

    def _add_hlz_zone(self, event: HLZCreatedEvent) -> None:
        """Add HLZ to zone tracking."""
        hlz = event.hlz

        # Skip if strength below threshold
        if hlz.strength < self.config.min_strength:
            return

        # Skip if already tracking max zones
        if len(self._active_zones) >= self.config.max_active_zones:
            return

        zone_meta = ZoneMeta(
            zone_id=hlz.hlz_id,
            zone_type=ZoneType.HLZ,
            top=hlz.top,
            bottom=hlz.bottom,
            strength=hlz.strength,
            side=hlz.side,
            timeframe="",  # HLZs span multiple timeframes
            created_at=event.timestamp,
        )

        self._active_zones[hlz.hlz_id] = zone_meta
        self._stats["zones_tracked"] += 1

    def _update_hlz_zone(self, event: HLZUpdatedEvent) -> None:
        """Update HLZ zone metadata."""
        if event.hlz_id not in self._active_zones:
            return

        hlz = event.hlz

        # Update zone metadata
        zone_meta = ZoneMeta(
            zone_id=hlz.hlz_id,
            zone_type=ZoneType.HLZ,
            top=hlz.top,
            bottom=hlz.bottom,
            strength=hlz.strength,
            side=hlz.side,
            timeframe="",
            created_at=self._active_zones[event.hlz_id].created_at,
        )

        self._active_zones[event.hlz_id] = zone_meta

    def _remove_zone(self, zone_id: str) -> None:
        """Remove zone from tracking."""
        if zone_id in self._active_zones:
            del self._active_zones[zone_id]
            self._stats["zones_expired"] += 1

    def _is_price_in_zone(self, price: float, zone_meta: ZoneMeta) -> bool:
        """Check if price is within zone boundaries."""
        zone_min = min(zone_meta.bottom, zone_meta.top) - self.config.price_tolerance
        zone_max = max(zone_meta.bottom, zone_meta.top) + self.config.price_tolerance
        return zone_min <= price <= zone_max

    def _infer_pool_side(self, pool: Any) -> str:  # LiquidityPool type
        """Infer pool side from pool properties."""
        # This is a heuristic - in production this should come from the detector
        # that created the pool or be stored as a pool attribute
        return "bullish"  # Default for now

    def _infer_direction(self, side: str) -> SignalDirection:
        """Convert zone side to signal direction."""
        match side.lower():
            case "bullish":
                return SignalDirection.LONG
            case "bearish":
                return SignalDirection.SHORT
            case _:
                return SignalDirection.LONG  # Default to long for neutral zones
