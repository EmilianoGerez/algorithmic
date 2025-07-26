"""
Signal models and events for trading signal generation.

This module defines the core data structures for zone-entry events,
signal candidates, and trading signals. Optimized for FSM state transitions
and fast lookups in the ZoneWatcher.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

from core.entities import Candle
from core.indicators.snapshot import IndicatorSnapshot

__all__ = [
    "CandidateState",
    "ZoneType",
    "ZoneEnteredEvent",
    "SignalCandidate",
    "TradingSignal",
    "SignalDirection",
]


class CandidateState(Enum):
    """FSM states for signal candidates."""

    WAIT_EMA = "wait_ema"  # Waiting for EMA alignment
    FILTERS = "filters"  # Checking volume/killzone/regime filters
    READY = "ready"  # Signal validated, ready for execution
    EXPIRED = "expired"  # Candidate expired or invalidated


class ZoneType(Enum):
    """Type of zone that generated the signal candidate."""

    POOL = "pool"  # Individual liquidity pool
    HLZ = "hlz"  # High-Liquidity Zone (overlap)


class SignalDirection(Enum):
    """Trading signal direction."""

    LONG = "long"
    SHORT = "short"


@dataclass(slots=True, frozen=True)
class ZoneEnteredEvent:
    """Event emitted when price enters a liquidity zone."""

    zone_id: str  # Pool ID or HLZ ID
    zone_type: ZoneType
    entry_price: float
    timestamp: datetime
    timeframe: str  # Originating timeframe (for pools)
    strength: float  # Pool strength or HLZ aggregate strength
    side: str  # "bullish", "bearish", or "neutral"
    event_type: Literal["zone_entered"] = "zone_entered"


@dataclass(slots=True, frozen=True)
class SignalCandidate:
    """
    Signal candidate instance for FSM processing.

    Immutable design for thread-safety. State changes create new instances.
    """

    candidate_id: str  # Unique candidate identifier
    zone_id: str  # Source zone ID
    zone_type: ZoneType
    direction: SignalDirection
    entry_price: float
    strength: float
    state: CandidateState
    created_at: datetime
    expires_at: datetime
    last_bar_timestamp: datetime | None = None

    def with_state(
        self, new_state: CandidateState, bar_timestamp: datetime
    ) -> SignalCandidate:
        """Create new candidate instance with updated state."""
        return SignalCandidate(
            candidate_id=self.candidate_id,
            zone_id=self.zone_id,
            zone_type=self.zone_type,
            direction=self.direction,
            entry_price=self.entry_price,
            strength=self.strength,
            state=new_state,
            created_at=self.created_at,
            expires_at=self.expires_at,
            last_bar_timestamp=bar_timestamp,
        )


@dataclass(slots=True, frozen=True)
class TradingSignal:
    """Final validated trading signal ready for execution."""

    signal_id: str  # Unique signal identifier
    candidate_id: str  # Source candidate ID
    zone_id: str  # Source zone ID
    zone_type: ZoneType
    direction: SignalDirection
    symbol: str  # Trading symbol (e.g., "EURUSD", "BTCUSD")
    entry_price: float  # Zone entry price
    current_price: float  # Current market price when signal generated
    strength: float  # Zone strength
    confidence: float  # Signal confidence score (0.0-1.0)
    timestamp: datetime
    timeframe: str  # Originating timeframe
    metadata: dict[str, str | float]  # Additional signal context

    @property
    def is_long(self) -> bool:
        """Check if signal is for long position."""
        return self.direction == SignalDirection.LONG

    @property
    def is_short(self) -> bool:
        """Check if signal is for short position."""
        return self.direction == SignalDirection.SHORT


def generate_candidate_id(zone_id: str, timestamp: datetime) -> str:
    """Generate unique candidate ID from zone and timestamp."""
    ts_str = timestamp.strftime("%H%M%S%f")[:-3]  # HHMMSSmmm format
    return f"cand_{zone_id}_{ts_str}"


def generate_signal_id(candidate_id: str, timestamp: datetime) -> str:
    """Generate unique signal ID from candidate and timestamp."""
    ts_str = timestamp.strftime("%H%M%S%f")[:-3]  # HHMMSSmmm format
    return f"sig_{candidate_id}_{ts_str}"
