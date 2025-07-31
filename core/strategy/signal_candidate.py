"""
Signal candidate finite state machine for trading signal validation.

This module implements the FSM that processes signal candidates through
validation stages: WAIT_EMA → FILTERS → READY → EXPIRED.
Designed for fast execution with pure guard functions for easy testing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.entities import Candle
from core.indicators.regime import Regime
from core.indicators.snapshot import IndicatorSnapshot

from .signal_models import (
    CandidateState,
    SignalCandidate,
    SignalDirection,
    TradingSignal,
    generate_signal_id,
)

__all__ = [
    "CandidateConfig",
    "FSMGuards",
    "SignalCandidateFSM",
    "FSMResult",
]


@dataclass(slots=True, frozen=True)
class CandidateConfig:
    """Configuration for signal candidate FSM."""

    expiry_minutes: int = 120  # Candidate lifetime in minutes
    ema_alignment: bool = True  # Require EMA alignment
    ema_tolerance_pct: float = 0.0  # EMA tolerance buffer (0.002 = 0.2%)
    linger_minutes: int = 0  # Keep zone 'hot' after touch for EMA reclaim
    reclaim_requires_ema: bool = True  # Require EMA flip after zone touch
    volume_multiple: float = 1.2  # Minimum volume vs SMA
    killzone_start: str = "12:00"  # Killzone start time (UTC)
    killzone_end: str = "14:05"  # Killzone end time (UTC)
    regime_allowed: list[str] | None = None  # Allowed regime states


@dataclass(slots=True, frozen=True)
class FSMResult:
    """Result of FSM processing."""

    updated_candidate: SignalCandidate
    signal: TradingSignal | None = None  # Emitted if state -> READY
    expired: bool = False  # True if candidate expired


class FSMGuards:
    """Pure guard functions for FSM state transitions."""

    @staticmethod
    def ema_alignment_ok(
        bar: Candle,
        snapshot: IndicatorSnapshot,
        direction: SignalDirection,
        tolerance_pct: float = 0.0,
    ) -> bool:
        """
        Check if EMA alignment supports the signal direction.

        Args:
            bar: Current price bar
            snapshot: Indicator values
            direction: Signal direction
            tolerance_pct: Tolerance buffer as percentage (e.g., 0.002 for 0.2%)

        Returns:
            True if alignment is valid (within tolerance)
        """
        if snapshot.ema21 is None or snapshot.ema50 is None:
            return False

        ema21 = snapshot.ema21
        tolerance_amount = ema21 * tolerance_pct

        if direction == SignalDirection.LONG:
            # For long: price above EMA21 (with tolerance buffer below)
            threshold = ema21 - tolerance_amount
            return bar.close > threshold
        else:  # SHORT
            # For short: price below EMA21 (with tolerance buffer above)
            threshold = ema21 + tolerance_amount
            return bar.close < threshold

    @staticmethod
    def volume_ok(bar: Candle, snapshot: IndicatorSnapshot, multiple: float) -> bool:
        """Check if volume exceeds the required multiple of SMA."""
        # Explicit check: if multiple is 0, volume filter is disabled
        if multiple == 0:
            return True

        # If multiple is negative or None, fall back to disabled
        if multiple <= 0:
            return True

        if snapshot.volume_sma is None or snapshot.volume_sma <= 0:
            return True  # Skip check if no volume data

        return bar.volume >= (snapshot.volume_sma * multiple)

    @staticmethod
    def killzone_ok(bar: Candle, start_time: str, end_time: str) -> bool:
        """Check if current time is within the killzone window."""
        try:
            bar_time = bar.ts.strftime("%H:%M")
            return start_time <= bar_time <= end_time
        except (AttributeError, ValueError):
            return True  # Default to allowing if time parsing fails

    @staticmethod
    def regime_ok(
        snapshot: IndicatorSnapshot, allowed_regimes: list[str] | None
    ) -> bool:
        """Check if current market regime is allowed."""
        if not allowed_regimes or snapshot.regime is None:
            return True  # Skip check if no restrictions or no regime data

        # Convert Regime enum to string for comparison
        regime_str = {
            Regime.BULL: "bull",
            Regime.BEAR: "bear",
            Regime.NEUTRAL: "neutral",
        }.get(snapshot.regime, "neutral")

        return regime_str in allowed_regimes

    @staticmethod
    def is_expired(candidate: SignalCandidate, current_time: datetime) -> bool:
        """Check if candidate has expired."""
        return current_time >= candidate.expires_at


class SignalCandidateFSM:
    """
    Finite state machine for signal candidate processing.

    Processes candidates through validation stages and emits trading signals
    when all conditions are met. Designed for high-frequency execution.
    """

    def __init__(
        self,
        config: CandidateConfig,
        symbol: str,
        timeframe: str,
        ready_callback: Callable[[str, datetime], None] | None = None,
    ) -> None:
        """
        Initialize FSM with configuration.

        Args:
            config: FSM configuration
            symbol: Trading symbol from config
            timeframe: Data timeframe from config
            ready_callback: Optional callback function called when candidate becomes READY.
                           Should accept (zone_id: str, timestamp: datetime)
        """
        self.config = config
        self.symbol = symbol
        self.timeframe = timeframe
        self.guards = FSMGuards()
        self.ready_callback = ready_callback

    def process(
        self,
        candidate: SignalCandidate,
        bar: Candle,
        snapshot: IndicatorSnapshot,
    ) -> FSMResult:
        """
        Process candidate through FSM state transitions.

        Args:
            candidate: Current candidate state
            bar: Current price bar
            snapshot: Indicator values snapshot

        Returns:
            FSMResult with updated candidate and optional signal
        """
        # Check for expiry first (any state can expire)
        if self.guards.is_expired(candidate, bar.ts):
            return FSMResult(
                updated_candidate=candidate.with_state(CandidateState.EXPIRED, bar.ts),
                expired=True,
            )

        # Process based on current state
        match candidate.state:
            case CandidateState.WAIT_EMA:
                return self._process_wait_ema(candidate, bar, snapshot)

            case CandidateState.TOUCH_CONF:
                return self._process_touch_conf(candidate, bar, snapshot)

            case CandidateState.FILTERS:
                return self._process_filters(candidate, bar, snapshot)

            case CandidateState.READY | CandidateState.EXPIRED:
                # Terminal states - no further processing
                return FSMResult(updated_candidate=candidate)

            case _:
                # Default case - no state change
                return FSMResult(updated_candidate=candidate)

    def _process_wait_ema(
        self, candidate: SignalCandidate, bar: Candle, snapshot: IndicatorSnapshot
    ) -> FSMResult:
        """Process WAIT_EMA state - check for EMA alignment or zone touch."""
        # Check if zone is touched for touch-&-reclaim pattern
        if self.config.linger_minutes > 0 and self._zone_touched(candidate, bar):
            # Move to TOUCH_CONF state with linger window
            return FSMResult(
                updated_candidate=candidate.with_state(
                    CandidateState.TOUCH_CONF, bar.ts
                )
            )

        # Check EMA alignment with tolerance buffer
        if self.config.ema_alignment and not self.guards.ema_alignment_ok(
            bar, snapshot, candidate.direction, self.config.ema_tolerance_pct
        ):
            # Stay in WAIT_EMA
            return FSMResult(
                updated_candidate=candidate.with_state(CandidateState.WAIT_EMA, bar.ts)
            )

        # EMA alignment OK (or not required) - move to FILTERS
        return FSMResult(
            updated_candidate=candidate.with_state(CandidateState.FILTERS, bar.ts)
        )

    def _process_touch_conf(
        self, candidate: SignalCandidate, bar: Candle, snapshot: IndicatorSnapshot
    ) -> FSMResult:
        """Process TOUCH_CONF state - waiting for EMA reclaim within linger window."""
        # Check if linger window has expired
        linger_window = timedelta(minutes=self.config.linger_minutes)
        last_update = candidate.last_bar_timestamp or candidate.created_at
        if bar.ts - last_update > linger_window:
            # Linger window expired - move to EXPIRED
            return FSMResult(
                updated_candidate=candidate.with_state(CandidateState.EXPIRED, bar.ts),
                expired=True,
            )

        # Check if EMA has been reclaimed
        ema_reclaimed = True
        if self.config.reclaim_requires_ema:
            # Use stricter EMA alignment for reclaim (no tolerance)
            ema_reclaimed = self.guards.ema_alignment_ok(
                bar, snapshot, candidate.direction, tolerance_pct=0.0
            )

        if ema_reclaimed:
            # EMA reclaimed - move to FILTERS
            return FSMResult(
                updated_candidate=candidate.with_state(CandidateState.FILTERS, bar.ts)
            )

        # Still waiting for reclaim - stay in TOUCH_CONF
        return FSMResult(
            updated_candidate=candidate.with_state(CandidateState.TOUCH_CONF, bar.ts)
        )

    def _process_filters(
        self, candidate: SignalCandidate, bar: Candle, snapshot: IndicatorSnapshot
    ) -> FSMResult:
        """Process FILTERS state."""
        # Check all filter conditions
        volume_ok = self.guards.volume_ok(bar, snapshot, self.config.volume_multiple)
        killzone_ok = self.guards.killzone_ok(
            bar, self.config.killzone_start, self.config.killzone_end
        )
        regime_ok = self.guards.regime_ok(
            snapshot, self.config.regime_allowed or ["bull", "neutral"]
        )

        if volume_ok and killzone_ok and regime_ok:
            # All filters passed - generate signal and move to READY
            signal = self._create_trading_signal(candidate, bar, snapshot)

            # Notify ZoneWatcher for entry spacing tracking
            if self.ready_callback:
                self.ready_callback(candidate.zone_id, bar.ts)

            return FSMResult(
                updated_candidate=candidate.with_state(CandidateState.READY, bar.ts),
                signal=signal,
            )
        else:
            # Filters failed - stay in FILTERS (will eventually expire)
            return FSMResult(
                updated_candidate=candidate.with_state(CandidateState.FILTERS, bar.ts)
            )

    def _create_trading_signal(
        self, candidate: SignalCandidate, bar: Candle, snapshot: IndicatorSnapshot
    ) -> TradingSignal:
        """Create trading signal from validated candidate."""
        # Calculate confidence based on strength and EMA distance
        confidence = min(1.0, candidate.strength / 10.0)  # Normalize strength to 0-1

        return TradingSignal(
            signal_id=generate_signal_id(candidate.candidate_id, bar.ts),
            candidate_id=candidate.candidate_id,
            zone_id=candidate.zone_id,
            zone_type=candidate.zone_type,
            direction=candidate.direction,
            symbol=self.symbol,
            entry_price=candidate.entry_price,
            current_price=bar.close,
            strength=candidate.strength,
            confidence=confidence,
            timestamp=bar.ts,
            timeframe=self.timeframe,
            metadata={
                "ema21": snapshot.ema21 or 0.0,
                "ema50": snapshot.ema50 or 0.0,
                "volume": bar.volume,
                "volume_sma": snapshot.volume_sma or 0.0,
            },
        )

    def create_candidate(
        self,
        zone_id: str,
        zone_type: str,
        direction: SignalDirection,
        entry_price: float,
        strength: float,
        timestamp: datetime,
    ) -> SignalCandidate:
        """Create new signal candidate."""
        from .signal_models import ZoneType, generate_candidate_id

        expires_at = timestamp + timedelta(minutes=self.config.expiry_minutes)

        return SignalCandidate(
            candidate_id=generate_candidate_id(zone_id, timestamp),
            zone_id=zone_id,
            zone_type=ZoneType(zone_type),
            direction=direction,
            entry_price=entry_price,
            strength=strength,
            state=CandidateState.WAIT_EMA,
            created_at=timestamp,
            expires_at=expires_at,
        )

    def _zone_touched(self, candidate: SignalCandidate, bar: Candle) -> bool:
        """
        Check if the liquidity zone has been touched by price action.

        Args:
            candidate: Signal candidate with zone information
            bar: Current price bar

        Returns:
            True if zone has been touched
        """
        entry_price = candidate.entry_price

        if candidate.direction == SignalDirection.LONG:
            # For longs: zone touched when price reaches or goes below entry
            # (spring/stop-hunt pattern before reclaim)
            return bar.low <= entry_price
        else:  # SHORT
            # For shorts: zone touched when price reaches or goes above entry
            # (spring/stop-hunt pattern before reclaim)
            return bar.high >= entry_price
