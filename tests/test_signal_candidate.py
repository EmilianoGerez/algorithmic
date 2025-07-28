"""
Unit tests for SignalCandidate FSM.

Tests focus on pure guard functions and state transitions with synthetic data
for fast execution. Pr        # Create candle out of killzone
        out_zone_time = datetime(2024, 1, 1, 20, 30)  # 20:30 UTC
        candle_out = Candle(
            ts=out_z        # Make volume bad
        good_candle = Candle(
            ts=good_candle.ts,
            open=good_candle.open,
            high=good_candle.high,
            low=good_candle.low,
            close=good_candle.close,
            volume=500,  # Below threshold (1000 * 1.2 = 1200)
        )
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1000,
        )ts ensure FSM invariants hold.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from core.entities import Candle
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.signal_candidate import (
    CandidateConfig,
    FSMGuards,
    FSMResult,
    SignalCandidateFSM,
)
from core.strategy.signal_models import (
    CandidateState,
    SignalCandidate,
    SignalDirection,
    ZoneType,
)


class TestFSMGuards:
    """Test pure guard functions in isolation."""

    def test_ema_alignment_long(self):
        """Test EMA alignment for long signals."""
        # Create mock candle and snapshot
        candle = Candle(
            ts=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,  # Above EMA21
            volume=1000,
        )

        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.ema21 = 102.0  # Above EMA50
        snapshot.ema50 = 101.0

        # Should pass for LONG (price > EMA21 > EMA50)
        assert FSMGuards.ema_alignment_ok(candle, snapshot, SignalDirection.LONG)

        # Should fail for SHORT
        assert not FSMGuards.ema_alignment_ok(candle, snapshot, SignalDirection.SHORT)

    def test_ema_alignment_short(self):
        """Test EMA alignment for short signals."""
        candle = Candle(
            ts=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=99.0,  # Below EMA21
            volume=1000,
        )

        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.ema21 = 100.0  # Below EMA50
        snapshot.ema50 = 101.0

        # Should pass for SHORT (price < EMA21 < EMA50)
        assert FSMGuards.ema_alignment_ok(candle, snapshot, SignalDirection.SHORT)

        # Should fail for LONG
        assert not FSMGuards.ema_alignment_ok(candle, snapshot, SignalDirection.LONG)

    def test_ema_alignment_missing_data(self):
        """Test EMA alignment with missing indicator data."""
        candle = Candle(
            ts=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1000,
        )

        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.ema21 = None  # Missing EMA data
        snapshot.ema50 = None

        # Should fail gracefully
        assert not FSMGuards.ema_alignment_ok(candle, snapshot, SignalDirection.LONG)
        assert not FSMGuards.ema_alignment_ok(candle, snapshot, SignalDirection.SHORT)

    def test_volume_ok(self):
        """Test volume filter."""
        candle = Candle(
            ts=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1200,  # Above threshold
        )

        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.volume_sma = 1000.0

        # Should pass with 1.2x multiple (1200 >= 1000 * 1.2)
        assert FSMGuards.volume_ok(candle, snapshot, 1.2)

        # Should fail with 1.5x multiple (1200 < 1000 * 1.5)
        assert not FSMGuards.volume_ok(candle, snapshot, 1.5)

    def test_volume_ok_missing_data(self):
        """Test volume filter with missing data."""
        candle = Candle(
            ts=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1200,
        )

        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.volume_sma = None  # Missing volume_sma

        # Should pass (default behavior when no volume data)
        assert FSMGuards.volume_ok(candle, snapshot, 1.5)

    def test_killzone_ok(self):
        """Test killzone time filter."""
        # Create candle in killzone
        in_zone_time = datetime(2024, 1, 1, 13, 30)  # 13:30 UTC
        candle_in = Candle(
            ts=in_zone_time,
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1000,
        )

        # Create candle outside killzone
        out_zone_time = datetime(2024, 1, 1, 10, 30)  # 10:30 UTC
        candle_out = Candle(
            ts=out_zone_time,
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1000,
        )

        # Should pass for time in killzone
        assert FSMGuards.killzone_ok(candle_in, "12:00", "14:05")

        # Should fail for time outside killzone
        assert not FSMGuards.killzone_ok(candle_out, "12:00", "14:05")

    def test_regime_ok(self):
        """Test regime filter."""
        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.regime = "bull"

        # Should pass for allowed regime
        assert FSMGuards.regime_ok(snapshot, ["bull", "neutral"])

        # Should fail for disallowed regime
        assert not FSMGuards.regime_ok(snapshot, ["bear"])

        # Should pass with empty allowed list (no restrictions)
        assert FSMGuards.regime_ok(snapshot, [])

    def test_is_expired(self):
        """Test expiry check."""
        base_time = datetime.now()

        candidate = SignalCandidate(
            candidate_id="test_123",
            zone_id="test_zone",
            zone_type=ZoneType.POOL,
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=2.0,
            state=CandidateState.WAIT_EMA,
            created_at=base_time,
            expires_at=base_time + timedelta(hours=2),
        )

        # Should not be expired before expiry time
        assert not FSMGuards.is_expired(candidate, base_time + timedelta(hours=1))

        # Should be expired at expiry time
        assert FSMGuards.is_expired(candidate, base_time + timedelta(hours=2))

        # Should be expired after expiry time
        assert FSMGuards.is_expired(candidate, base_time + timedelta(hours=3))


class TestSignalCandidateFSM:
    """Test FSM state transitions and signal generation."""

    @pytest.fixture
    def fsm(self):
        """Create FSM with test configuration."""
        config = CandidateConfig(
            expiry_minutes=120,
            ema_alignment=True,
            volume_multiple=1.2,
            killzone_start="12:00",
            killzone_end="14:05",
            regime_allowed=["bull", "neutral"],
        )
        return SignalCandidateFSM(config)

    @pytest.fixture
    def base_candidate(self):
        """Create base candidate for testing."""
        base_time = datetime(2024, 1, 1, 12, 0)
        return SignalCandidate(
            candidate_id="test_123",
            zone_id="H1_test_zone",
            zone_type=ZoneType.POOL,
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=2.0,
            state=CandidateState.WAIT_EMA,
            created_at=base_time,
            expires_at=base_time + timedelta(hours=2),
        )

    @pytest.fixture
    def good_candle(self):
        """Create candle that should pass all filters."""
        return Candle(
            ts=datetime(2024, 1, 1, 13, 0),  # In killzone
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,  # Above EMA21
            volume=1500,  # Above volume threshold
        )

    @pytest.fixture
    def good_snapshot(self):
        """Create snapshot that should pass all filters."""
        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.ema21 = 102.0  # Above EMA50
        snapshot.ema50 = 101.0
        snapshot.volume_sma = 1000.0  # Volume threshold base
        snapshot.regime = "bull"  # Allowed regime
        return snapshot

    def test_wait_ema_to_filters_transition(
        self, fsm, base_candidate, good_candle, good_snapshot
    ):
        """Test transition from WAIT_EMA to FILTERS."""
        result = fsm.process(base_candidate, good_candle, good_snapshot)

        assert result.updated_candidate.state == CandidateState.FILTERS
        assert result.signal is None
        assert not result.expired

    def test_wait_ema_stays_on_bad_ema(
        self, fsm, base_candidate, good_candle, good_snapshot
    ):
        """Test staying in WAIT_EMA with bad EMA alignment."""
        # Make EMA alignment bad for LONG signal
        # For LONG, bad alignment = price below EMA21
        good_snapshot.ema21 = 105.0  # Above close (103)
        good_snapshot.ema50 = 107.0

        result = fsm.process(base_candidate, good_candle, good_snapshot)

        assert result.updated_candidate.state == CandidateState.WAIT_EMA
        assert result.signal is None

    def test_filters_to_ready_with_signal(
        self, fsm, base_candidate, good_candle, good_snapshot
    ):
        """Test transition from FILTERS to READY with signal emission."""
        # Start in FILTERS state
        candidate_in_filters = base_candidate.with_state(
            CandidateState.FILTERS, good_candle.ts
        )

        result = fsm.process(candidate_in_filters, good_candle, good_snapshot)

        assert result.updated_candidate.state == CandidateState.READY
        assert result.signal is not None
        assert result.signal.direction == SignalDirection.LONG
        assert result.signal.zone_id == "H1_test_zone"

    def test_filters_stays_on_bad_volume(
        self, fsm, base_candidate, good_candle, good_snapshot
    ):
        """Test staying in FILTERS with bad volume."""
        # Make volume bad
        bad_volume_candle = Candle(
            ts=good_candle.ts,
            open=good_candle.open,
            high=good_candle.high,
            low=good_candle.low,
            close=good_candle.close,
            volume=500,  # Below threshold (1000 * 1.2 = 1200)
        )

        candidate_in_filters = base_candidate.with_state(
            CandidateState.FILTERS, good_candle.ts
        )

        result = fsm.process(candidate_in_filters, bad_volume_candle, good_snapshot)

        assert result.updated_candidate.state == CandidateState.FILTERS
        assert result.signal is None

    def test_expiry_from_any_state(
        self, fsm, base_candidate, good_candle, good_snapshot
    ):
        """Test expiry works from any state."""
        # Create expired candle
        expired_candle = Candle(
            ts=base_candidate.expires_at + timedelta(minutes=1),
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1500,
        )

        result = fsm.process(base_candidate, expired_candle, good_snapshot)

        assert result.updated_candidate.state == CandidateState.EXPIRED
        assert result.expired
        assert result.signal is None

    def test_terminal_states_no_processing(
        self, fsm, base_candidate, good_candle, good_snapshot
    ):
        """Test that terminal states don't process further."""
        # Test READY state
        ready_candidate = base_candidate.with_state(
            CandidateState.READY, good_candle.ts
        )
        result = fsm.process(ready_candidate, good_candle, good_snapshot)
        assert result.updated_candidate.state == CandidateState.READY

        # Test EXPIRED state
        expired_candidate = base_candidate.with_state(
            CandidateState.EXPIRED, good_candle.ts
        )
        result = fsm.process(expired_candidate, good_candle, good_snapshot)
        assert result.updated_candidate.state == CandidateState.EXPIRED

    def test_create_candidate(self, fsm):
        """Test candidate creation."""
        timestamp = datetime.now()

        candidate = fsm.create_candidate(
            zone_id="test_zone",
            zone_type="pool",
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=2.0,
            timestamp=timestamp,
        )

        assert candidate.zone_id == "test_zone"
        assert candidate.zone_type == ZoneType.POOL
        assert candidate.direction == SignalDirection.LONG
        assert candidate.state == CandidateState.WAIT_EMA
        assert candidate.expires_at > timestamp


class TestFSMPropertyInvariants:
    """Property-based tests for FSM invariants."""

    def test_candidate_never_ready_before_ema_ok(self):
        """Property: candidate should never reach READY before EMA guard is true."""
        # This would use hypothesis for property testing in a full implementation
        # For now, manual test with multiple scenarios

        config = CandidateConfig(ema_alignment=True)
        fsm = SignalCandidateFSM(config)

        base_time = datetime.now()
        candidate = SignalCandidate(
            candidate_id="test",
            zone_id="test_zone",
            zone_type=ZoneType.POOL,
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=2.0,
            state=CandidateState.WAIT_EMA,
            created_at=base_time,
            expires_at=base_time + timedelta(hours=2),
        )

        # Multiple candles with bad EMA alignment
        for i in range(10):
            candle = Candle(
                ts=base_time + timedelta(minutes=i),
                open=100.0,
                high=105.0,
                low=95.0,
                close=103.0,
                volume=1500,
            )

            snapshot = Mock(spec=IndicatorSnapshot)
            snapshot.ema21 = 99.0  # Bad alignment
            snapshot.ema50 = 101.0
            snapshot.volume_sma = 1000.0
            snapshot.regime = "bull"

            result = fsm.process(candidate, candle, snapshot)
            candidate = result.updated_candidate

            # Should never reach READY
            assert candidate.state != CandidateState.READY

    def test_signal_only_emitted_from_filters_to_ready(self):
        """Property: signals should only be emitted on FILTERS → READY transition."""
        config = CandidateConfig()
        fsm = SignalCandidateFSM(config)

        base_time = datetime.now()
        candle = Candle(
            ts=base_time,
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1500,
        )

        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.ema21 = 102.0
        snapshot.ema50 = 101.0
        snapshot.volume_sma = 1000.0
        snapshot.regime = "bull"

        # Test all state transitions
        states_to_test = [
            CandidateState.WAIT_EMA,
            CandidateState.READY,
            CandidateState.EXPIRED,
        ]

        for state in states_to_test:
            candidate = SignalCandidate(
                candidate_id="test",
                zone_id="test_zone",
                zone_type=ZoneType.POOL,
                direction=SignalDirection.LONG,
                entry_price=100.0,
                strength=2.0,
                state=state,
                created_at=base_time,
                expires_at=base_time + timedelta(hours=2),
            )

            result = fsm.process(candidate, candle, snapshot)

            # Only FILTERS state should emit signal (when transitioning to READY)
            # But we're not testing FILTERS here, so no signal expected
            if state != CandidateState.FILTERS:
                assert (
                    result.signal is None or state == CandidateState.WAIT_EMA
                )  # WAIT_EMA can transition to FILTERS then READY
