"""
Signal models and events for trading signal generation.

This module defines the core data structures for zone-entry events,
signal candidates, and trading signals. Optimized for FSM state transitions
and fast lookups in the ZoneWatcher.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal

from core.entities import Candle
from core.indicators.snapshot import IndicatorSnapshot

if TYPE_CHECKING:
    from .signal_candidate import SignalCandidateFSM

__all__ = [
    "CandidateState",
    "ZoneType",
    "ZoneEnteredEvent",
    "SignalCandidate",
    "TradingSignal",
    "SignalDirection",
    "calc_confidence",
]


def calc_confidence(filters_passed: int, total_filters: int) -> float:
    """Calculate signal confidence based on filter pass rate.

    Args:
        filters_passed: Number of filters that passed
        total_filters: Total number of filters evaluated

    Returns:
        Confidence score between 0.0 and 1.0
    """
    if total_filters == 0:
        return 0.5  # Default confidence when no filters

    base_confidence = filters_passed / total_filters

    # Apply scaling to give bonus for high pass rates
    if base_confidence >= 0.8:
        return min(1.0, base_confidence * 1.1)  # Boost high-confidence signals
    elif base_confidence <= 0.3:
        return max(0.1, base_confidence * 0.8)  # Penalize low-confidence signals
    else:
        return base_confidence


class CandidateState(Enum):
    """FSM states for signal candidates."""

    WAIT_EMA = "wait_ema"  # Waiting for EMA alignment
    TOUCH_CONF = "touch_conf"  # Zone touched, waiting for EMA reclaim (linger)
    FILTERS = "filters"  # Checking volume/killzone/regime filters
    READY = "ready"  # Signal validated, ready for execution
    SPACED_OUT = "spaced_out"  # Throttled due to entry spacing rules
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

    def is_ready(self) -> bool:
        """Check if candidate is ready for trading signal execution."""
        return self.state is CandidateState.READY

    def update(
        self,
        candle: Candle,
        indicators: IndicatorSnapshot,
        fsm: SignalCandidateFSM | None = None,
    ) -> SignalCandidate:
        """Update candidate state through FSM processing.

        Args:
            candle: Current price bar
            indicators: Indicator snapshot
            fsm: Signal candidate FSM instance

        Returns:
            Updated candidate with new state
        """
        if fsm is None:
            # Return self if no FSM provided (placeholder behavior)
            return self

        # Process through FSM
        result = fsm.process(self, candle, indicators)
        return result.updated_candidate

    def to_signal(
        self,
        symbol: str,
        timeframe: str,
        current_price: float,
        filters_passed: int,
        total_filters: int,
        entry_timestamp: datetime | None = None,
    ) -> TradingSignal:
        """Convert ready candidate to trading signal.

        Args:
            symbol: Trading symbol from config
            timeframe: Originating timeframe from config
            current_price: Current market price from IndicatorSnapshot
            filters_passed: Number of filters that passed validation
            total_filters: Total number of filters evaluated
            entry_timestamp: Optional timestamp for entry time (defaults to now)

        Returns:
            TradingSignal ready for broker submission
        """
        from datetime import datetime

        if not self.is_ready():
            raise ValueError(
                f"Candidate {self.candidate_id} not ready for signal conversion"
            )

        # Convert direction to side for broker compatibility
        side = "buy" if self.direction == SignalDirection.LONG else "sell"

        # Use provided entry timestamp or current UTC time
        signal_timestamp = entry_timestamp or datetime.now(UTC)

        # Calculate confidence based on filter performance
        confidence = calc_confidence(filters_passed, total_filters)

        return TradingSignal(
            signal_id=generate_signal_id(self.candidate_id, signal_timestamp),
            candidate_id=self.candidate_id,
            zone_id=self.zone_id,
            zone_type=self.zone_type,
            direction=self.direction,
            symbol=symbol,
            entry_price=self.entry_price,
            current_price=current_price,
            strength=self.strength,
            confidence=confidence,
            timestamp=signal_timestamp,
            timeframe=timeframe,
            metadata={
                "side": side,
                "entry_ts": signal_timestamp.isoformat(),
            },  # Add entry timestamp
        )

    def mark_spaced(self) -> SignalCandidate:
        """Mark candidate as spaced out due to throttling rules.

        Returns:
            New candidate instance with SPACED_OUT state
        """
        return SignalCandidate(
            candidate_id=self.candidate_id,
            zone_id=self.zone_id,
            zone_type=self.zone_type,
            direction=self.direction,
            entry_price=self.entry_price,
            strength=self.strength,
            state=CandidateState.SPACED_OUT,
            created_at=self.created_at,
            expires_at=self.expires_at,
            last_bar_timestamp=self.last_bar_timestamp,
        )

    def mark_submitted(self, order_id: str) -> None:
        """Mark candidate as submitted with order ID."""
        # For immutable design, this could update metadata or state
        pass


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

    @property
    def side(self) -> str:
        """Get trading side as string for broker compatibility."""
        return "buy" if self.is_long else "sell"

    @property
    def stop_loss(self) -> float:
        """Calculate stop loss based on entry price and ATR."""
        # Simple ATR-based stop loss (1.5x ATR)
        atr_multiple = 1.5
        estimated_atr = self.entry_price * 0.01  # 1% as rough ATR estimate

        if self.is_long:
            return self.entry_price - (estimated_atr * atr_multiple)
        else:
            return self.entry_price + (estimated_atr * atr_multiple)

    @property
    def take_profit(self) -> float:
        """Calculate take profit based on 2:1 risk/reward ratio."""
        risk_distance = abs(self.entry_price - self.stop_loss)

        if self.is_long:
            return self.entry_price + (risk_distance * 2.0)
        else:
            return self.entry_price - (risk_distance * 2.0)


def generate_candidate_id(zone_id: str, timestamp: datetime) -> str:
    """Generate unique candidate ID from zone and timestamp."""
    ts_str = timestamp.strftime("%H%M%S%f")[:-3]  # HHMMSSmmm format
    return f"cand_{zone_id}_{ts_str}"


def generate_signal_id(candidate_id: str, timestamp: datetime) -> str:
    """Generate unique signal ID from candidate and timestamp."""
    ts_str = timestamp.strftime("%H%M%S%f")[:-3]  # HHMMSSmmm format
    return f"sig_{candidate_id}_{ts_str}"
