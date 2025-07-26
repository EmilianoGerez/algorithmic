"""
High-Liquidity Zone (HLZ) overlap detection using interval trees.

Provides efficient O(log n) spatial queries for detecting overlapping
liquidity pools across multiple timeframes and generates HLZ events
when confluence criteria are met.
"""

from __future__ import annotations

import bisect
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .pool_registry import PoolRegistry

from .pool_models import (
    HighLiquidityZone,
    HLZCreatedEvent,
    HLZExpiredEvent,
    HLZUpdatedEvent,
    LiquidityPool,
    generate_hlz_id,
)

__all__ = [
    "OverlapConfig",
    "OverlapIndex",
    "OverlapDetector",
    "OverlapResult",
]


logger = logging.getLogger(__name__)


@dataclass
class OverlapConfig:
    """Configuration for HLZ overlap detection."""

    # HLZ creation thresholds
    min_members: int = 2
    min_strength: float = 3.0

    # Timeframe weighting for strength calculation
    tf_weight: dict[str, float] = field(
        default_factory=lambda: {
            "H1": 1.0,
            "H4": 2.0,
            "D1": 3.0,
        }
    )

    # Overlap detection settings
    merge_tolerance: float = 0.5  # Points - merge if zones within tolerance
    side_mixing: bool = False  # Allow bullish/bearish mixing in same HLZ

    # Performance limits
    max_active_hlzs: int = 1000
    recompute_on_update: bool = True


@dataclass(slots=True)
class Interval:
    """Price interval with pool reference for interval tree."""

    start: float  # Bottom price
    end: float  # Top price
    pool_id: str  # Reference to pool (avoid duplicate state)
    side: str  # "bullish" or "bearish"
    timeframe: str

    def overlaps(self, other: Interval) -> bool:
        """Check if this interval overlaps with another."""
        return self.start < other.end and other.start < self.end

    def contains_point(self, price: float) -> bool:
        """Check if price falls within this interval."""
        return self.start <= price <= self.end


@dataclass
class OverlapResult:
    """Result of overlap detection query."""

    overlapping_pools: list[str]
    overlap_region: tuple[float, float]  # (bottom, top)
    total_strength: float
    timeframes: set[str]
    sides: set[str]


class OverlapIndex:
    """
    Efficient interval tree for overlap detection.

    Maintains separate sorted lists per side to avoid mixing
    bullish/bearish pools during strength aggregation.
    Uses bisect for O(log n) insertion and O(k log n) overlap queries.
    """

    def __init__(self, side_mixing: bool = False):
        self.side_mixing = side_mixing

        # Separate interval lists per side for clean aggregation
        self._bullish_intervals: list[Interval] = []
        self._bearish_intervals: list[Interval] = []

        # Quick lookup for removal
        self._pool_to_interval: dict[str, Interval] = {}

    def add_interval(self, interval: Interval) -> None:
        """Add interval to the appropriate sorted list."""
        if interval.pool_id in self._pool_to_interval:
            # Pool already exists - remove old interval first
            self.remove_interval(interval.pool_id)

        # Insert into appropriate side list (keep sorted by start price)
        if interval.side == "bullish":
            bisect.insort(self._bullish_intervals, interval, key=lambda x: x.start)
        elif interval.side == "bearish":
            bisect.insort(self._bearish_intervals, interval, key=lambda x: x.start)
        else:
            logger.warning(f"Unknown interval side: {interval.side}")
            return

        self._pool_to_interval[interval.pool_id] = interval

    def remove_interval(self, pool_id: str) -> bool:
        """Remove interval by pool ID."""
        if pool_id not in self._pool_to_interval:
            return False

        interval = self._pool_to_interval[pool_id]

        # Remove from appropriate side list
        if interval.side == "bullish":
            self._bullish_intervals.remove(interval)
        elif interval.side == "bearish":
            self._bearish_intervals.remove(interval)

        del self._pool_to_interval[pool_id]
        return True

    def query_overlaps(self, target_interval: Interval) -> OverlapResult:
        """Find all intervals that overlap with target interval."""
        overlapping_intervals = []

        # Query same side first
        if target_interval.side == "bullish":
            overlapping_intervals.extend(
                self._find_overlaps_in_list(target_interval, self._bullish_intervals)
            )

            # Include bearish if side mixing allowed
            if self.side_mixing:
                overlapping_intervals.extend(
                    self._find_overlaps_in_list(
                        target_interval, self._bearish_intervals
                    )
                )
        elif target_interval.side == "bearish":
            overlapping_intervals.extend(
                self._find_overlaps_in_list(target_interval, self._bearish_intervals)
            )

            # Include bullish if side mixing allowed
            if self.side_mixing:
                overlapping_intervals.extend(
                    self._find_overlaps_in_list(
                        target_interval, self._bullish_intervals
                    )
                )

        if not overlapping_intervals:
            return OverlapResult([], (0.0, 0.0), 0.0, set(), set())

        # Calculate overlap region (intersection of all overlapping intervals)
        min_start = max(interval.start for interval in overlapping_intervals)
        max_end = min(interval.end for interval in overlapping_intervals)

        # Collect metadata
        pool_ids = [interval.pool_id for interval in overlapping_intervals]
        timeframes = {interval.timeframe for interval in overlapping_intervals}
        sides = {interval.side for interval in overlapping_intervals}

        return OverlapResult(
            overlapping_pools=pool_ids,
            overlap_region=(min_start, max_end),
            total_strength=0.0,  # Will be calculated by OverlapDetector
            timeframes=timeframes,
            sides=sides,
        )

    def _find_overlaps_in_list(
        self, target: Interval, interval_list: list[Interval]
    ) -> list[Interval]:
        """Find overlapping intervals in a sorted list using binary search."""
        if not interval_list:
            return []

        overlaps = []

        # Find insertion point for target start (all intervals to the left end before target)
        left_idx = bisect.bisect_left(interval_list, target.start, key=lambda x: x.end)

        # Check intervals from left_idx onwards until no more overlaps
        for i in range(left_idx, len(interval_list)):
            interval = interval_list[i]

            # If interval starts after target ends, no more overlaps possible
            if interval.start >= target.end:
                break

            # Check if actually overlaps
            if interval.overlaps(target):
                overlaps.append(interval)

        return overlaps

    def get_all_pools(self) -> list[str]:
        """Get all pool IDs in the index."""
        return list(self._pool_to_interval.keys())

    def size(self) -> int:
        """Get total number of intervals in the index."""
        return len(self._pool_to_interval)


class OverlapDetector:
    """
    Detects overlapping liquidity pools and generates HLZ events.

    Maintains interval trees per side and reacts to pool lifecycle
    events to create, update, or expire High-Liquidity Zones.
    """

    def __init__(
        self,
        config: OverlapConfig | None = None,
        registry: PoolRegistry | None = None,
    ):
        self.config = config or OverlapConfig()
        self._registry = registry  # For accessing pool data

        # Interval tree for spatial queries
        self._overlap_index = OverlapIndex(side_mixing=self.config.side_mixing)

        # HLZ tracking with O(1) lookups as suggested
        self._active_hlzs: dict[str, HighLiquidityZone] = {}
        self._hlz_members: dict[str, set[str]] = {}  # hlz_id -> pool_ids
        self._pool_to_hlzs: dict[str, set[str]] = defaultdict(set)  # pool_id -> hlz_ids

        # Track previous strength for HLZUpdated spam prevention
        self._hlz_strength_cache: dict[str, float] = {}

        # Statistics
        self._stats = {
            "hlzs_created": 0,
            "hlzs_expired": 0,
            "hlzs_updated": 0,
            "pools_processed": 0,
            "overlaps_detected": 0,
        }

    def on_pool_event(
        self, event: Any
    ) -> list[HLZCreatedEvent | HLZUpdatedEvent | HLZExpiredEvent]:
        """
        Handle pool lifecycle events from registry.

        This is the main entry point for registry integration via listeners.
        """
        if hasattr(event, "pool_id") and hasattr(event, "event_type"):
            if event.event_type == "created":
                # Get the pool from registry if available
                if self._registry:
                    pool = self._registry.get_pool(event.pool_id)
                    if pool:
                        return cast(
                            list[HLZCreatedEvent | HLZUpdatedEvent | HLZExpiredEvent],
                            self.on_pool_created(pool, event.timestamp),
                        )
                # If no registry, we can't process created events
                return []
            elif event.event_type == "touched":
                return cast(
                    list[HLZCreatedEvent | HLZUpdatedEvent | HLZExpiredEvent],
                    self.on_pool_touched(
                        event.pool_id, event.touch_price, event.timestamp
                    ),
                )
            elif event.event_type == "expired":
                return cast(
                    list[HLZCreatedEvent | HLZUpdatedEvent | HLZExpiredEvent],
                    self.on_pool_expired(event.pool_id, event.timestamp),
                )
        return []

    def on_pool_created(
        self, pool: LiquidityPool, timestamp: datetime
    ) -> list[HLZCreatedEvent | HLZUpdatedEvent]:
        """Handle pool creation and detect new overlaps."""
        self._stats["pools_processed"] += 1

        # Create interval for this pool
        interval = Interval(
            start=min(pool.bottom, pool.top),
            end=max(pool.bottom, pool.top),
            pool_id=pool.pool_id,
            side=self._infer_pool_side(pool),
            timeframe=pool.timeframe,
        )

        # Query existing overlaps before adding the new pool
        overlap_result = self._overlap_index.query_overlaps(interval)

        # Add the new pool to index
        self._overlap_index.add_interval(interval)

        events = []

        # Check if we can form new HLZs or update existing ones
        if overlap_result.overlapping_pools:
            # Include the new pool in potential HLZ
            all_pool_ids = [*overlap_result.overlapping_pools, pool.pool_id]
            hlz_events = self._process_pool_group(all_pool_ids, timestamp)
            events.extend(hlz_events)

        return events

    def on_pool_touched(
        self, pool_id: str, touch_price: float, timestamp: datetime
    ) -> list[HLZUpdatedEvent]:
        """
        Handle pool touch events.

        Currently, pool touches don't affect HLZ creation/destruction,
        but this method is provided for completeness and future extensions.
        """
        # For now, pool touches don't affect overlap detection
        # In future, we might update HLZ strength or track touch statistics
        return []

    def on_pool_expired(
        self, pool_id: str, timestamp: datetime
    ) -> list[HLZExpiredEvent | HLZUpdatedEvent]:
        """Handle pool expiry and update affected HLZs."""
        # Remove from interval tree
        removed = self._overlap_index.remove_interval(pool_id)
        if not removed:
            return []  # Pool wasn't in index

        events: list[HLZExpiredEvent | HLZUpdatedEvent] = []

        # Find affected HLZs
        affected_hlz_ids = self._pool_to_hlzs.get(pool_id, set()).copy()

        for hlz_id in affected_hlz_ids:
            # Remove pool from HLZ membership
            if hlz_id in self._hlz_members:
                self._hlz_members[hlz_id].discard(pool_id)

                # Check if HLZ still meets minimum requirements
                if len(self._hlz_members[hlz_id]) < self.config.min_members:
                    # Expire HLZ
                    expired_hlz = self._active_hlzs.pop(hlz_id, None)
                    if expired_hlz:
                        events.append(
                            HLZExpiredEvent(
                                hlz_id=hlz_id,
                                timestamp=timestamp,
                                final_member_count=len(self._hlz_members[hlz_id]),
                            )
                        )
                        self._stats["hlzs_expired"] += 1

                    # Clean up membership tracking
                    remaining_members = self._hlz_members.pop(hlz_id, set())
                    for member_id in remaining_members:
                        self._pool_to_hlzs[member_id].discard(hlz_id)
                else:
                    # HLZ still valid - update it
                    prev_strength = self._active_hlzs[
                        hlz_id
                    ].strength  # Get previous strength
                    updated_hlz = self._recompute_hlz(hlz_id, timestamp)
                    if updated_hlz:
                        events.append(
                            HLZUpdatedEvent(
                                hlz_id=hlz_id,
                                timestamp=timestamp,
                                hlz=updated_hlz,
                                prev_strength=prev_strength,
                            )
                        )

        # Clean up pool tracking (only if it exists)
        if pool_id in self._pool_to_hlzs:
            del self._pool_to_hlzs[pool_id]

        return events

    def _process_pool_group(
        self, pool_ids: list[str], timestamp: datetime
    ) -> list[HLZCreatedEvent | HLZUpdatedEvent]:
        """Process a group of potentially overlapping pools."""
        if len(pool_ids) < self.config.min_members:
            return []

        # Generate deterministic HLZ ID
        member_set = frozenset(pool_ids)
        hlz_id = generate_hlz_id(member_set)

        # Check if this HLZ already exists
        if hlz_id in self._active_hlzs:
            # HLZ exists - check if membership or strength changed
            current_members = self._hlz_members.get(hlz_id, set())
            if current_members != set(pool_ids):
                # Membership changed - recompute
                updated_hlz = self._recompute_hlz(hlz_id, timestamp)
                if updated_hlz:
                    # Check if strength actually changed to prevent spam
                    previous_strength = self._hlz_strength_cache.get(hlz_id, 0.0)
                    if abs(updated_hlz.strength - previous_strength) > 1e-6:
                        self._hlz_strength_cache[hlz_id] = updated_hlz.strength
                        self._stats["hlzs_updated"] += 1
                        return [
                            HLZUpdatedEvent(
                                hlz_id=hlz_id,
                                timestamp=timestamp,
                                hlz=updated_hlz,
                                prev_strength=previous_strength,
                            )
                        ]
            return []  # No significant change needed

        # New HLZ - create it
        hlz = self._create_hlz(pool_ids, timestamp)
        if hlz:
            # Store HLZ and update tracking
            self._active_hlzs[hlz_id] = hlz
            self._hlz_members[hlz_id] = set(pool_ids)
            self._hlz_strength_cache[hlz_id] = hlz.strength

            for pool_id in pool_ids:
                self._pool_to_hlzs[pool_id].add(hlz_id)

            self._stats["hlzs_created"] += 1

            return [
                HLZCreatedEvent(
                    hlz_id=hlz_id,
                    timestamp=timestamp,
                    hlz=hlz,
                )
            ]

        return []

    def _create_hlz(
        self, pool_ids: list[str], timestamp: datetime
    ) -> HighLiquidityZone | None:
        """Create HLZ from overlapping pools with strength aggregation."""
        if not self._registry or len(pool_ids) < self.config.min_members:
            return None

        # Get pools from registry
        pools = []
        for pool_id in pool_ids:
            pool = self._registry.get_pool(pool_id)
            if pool is None:
                logger.warning(f"Pool {pool_id} not found in registry")
                return None
            pools.append(pool)

        if not pools:
            return None

        # Calculate overlap region (intersection of all pools)
        min_start = max(min(pool.bottom, pool.top) for pool in pools)
        max_end = min(max(pool.bottom, pool.top) for pool in pools)

        if min_start >= max_end:
            # No actual overlap
            return None

        # Determine HLZ side (must be consistent unless side mixing allowed)
        sides = {self._infer_pool_side(pool) for pool in pools}
        if len(sides) > 1 and not self.config.side_mixing:
            # Mixed sides not allowed
            return None

        hlz_side = sides.pop() if len(sides) == 1 else "mixed"

        # Calculate weighted strength using TF weights
        total_strength = 0.0
        timeframes = set()

        for pool in pools:
            tf_weight = self.config.tf_weight.get(pool.timeframe, 1.0)
            weighted_strength = pool.strength * tf_weight
            total_strength += weighted_strength
            timeframes.add(pool.timeframe)

        # Check minimum strength threshold
        if total_strength < self.config.min_strength:
            return None

        # Generate HLZ ID
        member_set = frozenset(pool_ids)
        hlz_id = generate_hlz_id(member_set)

        # Create HLZ
        hlz = HighLiquidityZone(
            hlz_id=hlz_id,
            side=hlz_side,
            top=max_end,
            bottom=min_start,
            strength=total_strength,
            member_pool_ids=member_set,
            created_at=timestamp,
            timeframes=frozenset(timeframes),
        )

        return hlz

    def _recompute_hlz(
        self, hlz_id: str, timestamp: datetime
    ) -> HighLiquidityZone | None:
        """Recompute HLZ after membership change."""
        if hlz_id not in self._hlz_members:
            return None

        pool_ids = list(self._hlz_members[hlz_id])
        return self._create_hlz(pool_ids, timestamp)

    def _infer_pool_side(self, pool: LiquidityPool) -> str:
        """
        Infer pool side from pool properties.

        This is a heuristic since the pool doesn't store side directly.
        In a full implementation, this would come from the detector event
        that created the pool, or be stored as a pool attribute.
        """
        # For now, use a simple heuristic based on pool_id or strength
        # In practice, this should come from the detector event context
        if hasattr(pool, "side"):
            return str(pool.side)  # Ensure string return type

        # Fallback heuristic: try to parse from pool_id
        if "_bullish_" in pool.pool_id.lower() or "_bull_" in pool.pool_id.lower():
            return "bullish"
        elif "_bearish_" in pool.pool_id.lower() or "_bear_" in pool.pool_id.lower():
            return "bearish"

        # Default assumption for testing
        return "bullish"

    def get_active_hlzs(self) -> dict[str, HighLiquidityZone]:
        """Get all currently active HLZs."""
        return self._active_hlzs.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics."""
        return {
            **self._stats,
            "active_hlzs": len(self._active_hlzs),
            "total_pools": self._overlap_index.size(),
        }

    def get_prometheus_metrics(self) -> dict[str, float]:
        """Return HLZ metrics in Prometheus format."""
        return {
            # HLZ counters (mirroring pool metrics)
            "overlap_detector_hlz_created_total": float(self._stats["hlzs_created"]),
            "overlap_detector_hlz_updated_total": float(self._stats["hlzs_updated"]),
            "overlap_detector_hlz_expired_total": float(self._stats["hlzs_expired"]),
            # HLZ gauge (current active count)
            "overlap_detector_hlz_active": float(len(self._active_hlzs)),
        }
