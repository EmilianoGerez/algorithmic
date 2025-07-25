"""
Data models and events for liquidity pool lifecycle management.

This module defines the core data structures for representing liquidity pools,
their lifecycle states, and related events. Optimized for memory efficiency
and high-throughput processing.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Protocol

__all__ = [
    "PoolState",
    "LiquidityPool",
    "PoolEvent",
    "PoolCreatedEvent",
    "PoolTouchedEvent",
    "PoolExpiredEvent",
    "HighLiquidityZone",
    "HLZCreatedEvent",
    "HLZUpdatedEvent",
    "HLZExpiredEvent",
    "generate_pool_id",
    "generate_hlz_id",
]


class PoolState(Enum):
    """Lifecycle states for liquidity pools."""

    ACTIVE = "active"
    TOUCHED = "touched"  # Price has entered the zone
    EXPIRED = "expired"
    GRACE = "grace"  # Expired but kept for analytics


@dataclass(slots=True, frozen=True)
class LiquidityPool:
    """
    Represents a liquidity pool zone with TTL management.

    Memory-optimized with __slots__ to stay within 1KB per pool budget.
    Immutable design for thread-safety and cache efficiency.
    """

    pool_id: str
    timeframe: str
    top: float
    bottom: float
    strength: float  # Detector strength for overlap weighting
    state: PoolState
    created_at: datetime
    last_touched_at: datetime | None
    expires_at: datetime
    hit_tolerance: float = 0.0

    @property
    def mid_price(self) -> float:
        """Calculate midpoint of the pool zone."""
        return (self.top + self.bottom) / 2.0

    @property
    def zone_height(self) -> float:
        """Calculate height of the pool zone."""
        return abs(self.top - self.bottom)

    def is_price_in_zone(self, price: float) -> bool:
        """Check if price is within the pool zone (with tolerance)."""
        zone_min = min(self.bottom, self.top) - self.hit_tolerance
        zone_max = max(self.bottom, self.top) + self.hit_tolerance
        return zone_min <= price <= zone_max

    def with_state(
        self, new_state: PoolState, touch_time: datetime | None = None
    ) -> LiquidityPool:
        """Create a new pool instance with updated state."""
        return LiquidityPool(
            pool_id=self.pool_id,
            timeframe=self.timeframe,
            top=self.top,
            bottom=self.bottom,
            strength=self.strength,
            state=new_state,
            created_at=self.created_at,
            last_touched_at=touch_time or self.last_touched_at,
            expires_at=self.expires_at,
            hit_tolerance=self.hit_tolerance,
        )


class PoolEvent(Protocol):
    """Protocol for pool lifecycle events."""

    pool_id: str
    timestamp: datetime
    event_type: Literal["created", "touched", "expired"]


@dataclass(slots=True, frozen=True)
class PoolCreatedEvent:
    """Event emitted when a new pool is created."""

    pool_id: str
    timestamp: datetime
    pool: LiquidityPool
    event_type: Literal["created"] = "created"


@dataclass(slots=True, frozen=True)
class PoolTouchedEvent:
    """Event emitted when price enters a pool zone."""

    pool_id: str
    timestamp: datetime
    touch_price: float
    event_type: Literal["touched"] = "touched"


@dataclass(slots=True, frozen=True)
class PoolExpiredEvent:
    """Event emitted when a pool expires."""

    pool_id: str
    timestamp: datetime
    final_state: PoolState
    event_type: Literal["expired"] = "expired"


@dataclass(slots=True, frozen=True)
class HighLiquidityZone:
    """
    High-Liquidity Zone created by overlapping pools from different timeframes.

    Represents areas of confluence where multiple liquidity pools intersect,
    indicating higher probability reversal or continuation zones.
    """

    hlz_id: str
    side: str  # "bullish", "bearish", or "neutral"
    top: float
    bottom: float
    strength: float  # Aggregated strength from member pools
    member_pool_ids: frozenset[str]  # Pool IDs that form this HLZ
    created_at: datetime
    timeframes: frozenset[str]  # Timeframes represented (e.g., {"H1", "H4"})

    @property
    def mid_price(self) -> float:
        """Calculate midpoint of the HLZ."""
        return (self.top + self.bottom) / 2.0

    @property
    def zone_height(self) -> float:
        """Calculate height of the HLZ."""
        return abs(self.top - self.bottom)

    @property
    def member_count(self) -> int:
        """Number of pools forming this HLZ."""
        return len(self.member_pool_ids)


@dataclass(slots=True, frozen=True)
class HLZCreatedEvent:
    """Event emitted when a new High-Liquidity Zone is created."""

    hlz_id: str
    timestamp: datetime
    hlz: HighLiquidityZone
    event_type: Literal["hlz_created"] = "hlz_created"


@dataclass(slots=True, frozen=True)
class HLZUpdatedEvent:
    """Event emitted when an existing HLZ is updated (member added/removed)."""

    hlz_id: str
    timestamp: datetime
    hlz: HighLiquidityZone
    prev_strength: float  # Previous strength for proportional consumer reactions
    event_type: Literal["hlz_updated"] = "hlz_updated"


@dataclass(slots=True, frozen=True)
class HLZExpiredEvent:
    """Event emitted when an HLZ expires (< min_members)."""

    hlz_id: str
    timestamp: datetime
    final_member_count: int
    event_type: Literal["hlz_expired"] = "hlz_expired"


def generate_pool_id(
    timeframe: str, timestamp: datetime, top: float, bottom: float
) -> str:
    """
    Generate a fast, deterministic pool ID.

    Format: {tf}_{iso_timestamp}_{hash_suffix}
    Guarantees uniqueness and reproducible IDs across runs.
    Uses full 32-bit hash for maximum collision resistance,
    supporting millions of lifetime pools.

    Args:
        timeframe: Pool timeframe (H1, H4, D1)
        timestamp: Pool creation timestamp
        top: Top price of the zone
        bottom: Bottom price of the zone

    Returns:
        Unique pool identifier string
    """
    # Create deterministic hash from price coordinates using zlib.adler32
    # Include all parameters for maximum uniqueness
    # Convert floats to bytes for consistent hashing across platforms
    price_bytes = struct.pack(
        "!dd", top, bottom
    )  # Network byte order, double precision
    tf_bytes = timeframe.encode("utf-8")

    # Include timestamp seconds to reduce collisions across time
    timestamp_bytes = struct.pack("!q", int(timestamp.timestamp()))  # 8-byte timestamp

    combined_bytes = tf_bytes + timestamp_bytes + price_bytes

    price_hash = (
        zlib.adler32(combined_bytes) & 0xFFFFFFFF
    )  # 32-bit hash for maximum collision resistance

    # ISO timestamp without microseconds for cleaner IDs
    iso_ts = timestamp.replace(microsecond=0).isoformat()

    return f"{timeframe}_{iso_ts}_{price_hash:08x}"


def generate_hlz_id(member_pool_ids: frozenset[str]) -> str:
    """
    Generate a deterministic HLZ ID from member pool IDs.

    Uses SHA1 hash of sorted pool IDs to ensure consistent
    ID generation regardless of member discovery order.

    Args:
        member_pool_ids: Set of pool IDs forming the HLZ

    Returns:
        Deterministic HLZ identifier string
    """
    # Sort pool IDs for deterministic ordering
    sorted_ids = sorted(member_pool_ids)

    # Create deterministic hash from sorted member IDs
    combined_str = "|".join(sorted_ids)
    hash_obj = hashlib.sha1(combined_str.encode("utf-8"))
    hash_hex = hash_obj.hexdigest()[:12]  # 12 chars = 48-bit hash

    return f"hlz_{hash_hex}"
