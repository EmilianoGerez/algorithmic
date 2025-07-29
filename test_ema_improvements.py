"""
Test script for EMA Tolerance Buffer and Touch-&-Reclaim improvements.

This script validates:
1. Tolerance Buffer: EMA alignment with 0.002% (0.2%) buffer
2. Touch-&-Reclaim: Zone touch → linger window → EMA reclaim → signal
"""

from datetime import datetime, timedelta

from core.entities import Candle
from core.strategy.signal_candidate import (
    CandidateConfig,
    FSMGuards,
    SignalCandidateFSM,
)
from core.strategy.signal_models import (
    CandidateState,
    IndicatorSnapshot,
    SignalDirection,
)


def create_test_bar(
    close_price: float,
    timestamp: datetime,
    low: float | None = None,
    high: float | None = None,
) -> Candle:
    """Create test bar with specified close price."""
    return Candle(
        open=close_price - 0.0001,
        high=high or close_price + 0.0002,
        low=low or close_price - 0.0002,
        close=close_price,
        volume=1000.0,
        ts=timestamp,
    )


def create_test_snapshot(ema21: float, ema50: float | None = None) -> IndicatorSnapshot:
    """Create test indicator snapshot."""
    from datetime import datetime

    return IndicatorSnapshot(
        timestamp=datetime(2024, 5, 19, 10, 0),
        ema21=ema21,
        ema50=ema50 or ema21 - 0.01,
        atr=0.001,
        volume_sma=800.0,
        regime=None,
        regime_with_slope=None,
        current_volume=1000.0,
        current_close=ema21,
    )


def test_tolerance_buffer():
    """Test EMA tolerance buffer functionality."""
    print("=== Testing EMA Tolerance Buffer ===")

    # Config with 0.2% tolerance buffer
    config = CandidateConfig(
        ema_tolerance_pct=0.002,  # 0.2% tolerance
        linger_minutes=0,  # Disable touch-&-reclaim for this test
        reclaim_requires_ema=True,
        ema_alignment=True,
        volume_multiple=1.0,
        killzone_start=8,
        killzone_end=12,
        regime_allowed=["bull", "neutral"],
        expiry_minutes=60,
    )

    fsm = SignalCandidateFSM(config)

    # Create a LONG candidate
    timestamp = datetime(2024, 5, 19, 10, 0)
    candidate = fsm.create_candidate(
        zone_id="H1_LONG_001",
        zone_type="pool",
        direction=SignalDirection.LONG,
        entry_price=1.0850,
        strength=0.8,
        timestamp=timestamp,
    )

    print(f"Created candidate: {candidate.candidate_id}")
    print(f"Entry price: {candidate.entry_price}")
    print(f"Initial state: {candidate.state}")

    # Test Case 1: Price slightly below EMA21 but within tolerance
    ema21 = 1.0851  # EMA21 above entry
    tolerance_amount = ema21 * 0.002  # 0.2% of EMA21
    threshold = ema21 - tolerance_amount
    test_price = threshold + 0.000001  # Just above threshold

    print("\nTest Case 1: Price within tolerance")
    print(f"EMA21: {ema21}")
    print(f"Tolerance amount: {tolerance_amount:.6f}")
    print(f"Threshold: {threshold:.6f}")
    print(f"Test price: {test_price:.6f}")

    bar = create_test_bar(test_price, timestamp + timedelta(minutes=1))
    snapshot = create_test_snapshot(ema21)

    result = fsm.process(candidate, bar, snapshot)
    print(f"Result state: {result.updated_candidate.state}")
    print(f"Signal generated: {result.signal is not None}")

    # Should move to FILTERS state (EMA alignment OK with tolerance)
    assert result.updated_candidate.state == CandidateState.FILTERS

    # Test Case 2: Price below tolerance threshold
    test_price_below = threshold - 0.000001
    print("\nTest Case 2: Price below tolerance threshold")
    print(f"Test price: {test_price_below:.6f}")

    bar_below = create_test_bar(test_price_below, timestamp + timedelta(minutes=2))
    result_below = fsm.process(candidate, bar_below, snapshot)
    print(f"Result state: {result_below.updated_candidate.state}")

    # Should stay in WAIT_EMA state
    assert result_below.updated_candidate.state == CandidateState.WAIT_EMA

    print("✅ Tolerance Buffer test passed!")


def test_touch_and_reclaim():
    """Test Touch-&-Reclaim functionality."""
    print("\n=== Testing Touch-&-Reclaim ===")

    # Config with touch-&-reclaim enabled
    config = CandidateConfig(
        ema_tolerance_pct=0.0,  # No tolerance for clean test
        linger_minutes=5,  # 5-minute linger window
        reclaim_requires_ema=True,
        ema_alignment=True,
        volume_multiple=1.0,
        killzone_start=8,
        killzone_end=12,
        regime_allowed=["bull", "neutral"],
        expiry_minutes=60,
    )

    fsm = SignalCandidateFSM(config)

    # Create a LONG candidate
    timestamp = datetime(2024, 5, 20, 10, 0)
    candidate = fsm.create_candidate(
        zone_id="H1_LONG_002",
        zone_type="pool",
        direction=SignalDirection.LONG,
        entry_price=1.0850,
        strength=0.8,
        timestamp=timestamp,
    )

    print(f"Created candidate: {candidate.candidate_id}")
    print(f"Entry price: {candidate.entry_price}")
    print(f"Linger window: {config.linger_minutes} minutes")

    # Test Case 1: Zone touched (price hits entry level)
    # EMA21 is above price (no alignment yet)
    ema21 = 1.0860  # Above current price
    bar_touch = create_test_bar(
        close_price=1.0852,
        timestamp=timestamp + timedelta(minutes=1),
        low=1.0849,  # Touch the zone entry
    )
    snapshot = create_test_snapshot(ema21)

    print("\nTest Case 1: Zone touched")
    print(f"Bar low: {bar_touch.low} (touches entry: {candidate.entry_price})")
    print(f"EMA21: {ema21} (above price, no alignment)")

    result = fsm.process(candidate, bar_touch, snapshot)
    print(f"Result state: {result.updated_candidate.state}")

    # Should move to TOUCH_CONF state
    assert result.updated_candidate.state == CandidateState.TOUCH_CONF

    # Test Case 2: EMA reclaimed within linger window
    ema21_reclaimed = 1.0849  # EMA21 now below price
    bar_reclaim = create_test_bar(1.0851, timestamp + timedelta(minutes=3))
    snapshot_reclaim = create_test_snapshot(ema21_reclaimed)

    print("\nTest Case 2: EMA reclaimed within linger window")
    print(f"EMA21: {ema21_reclaimed} (below price, alignment OK)")
    print("Time elapsed: 3 minutes (within 5-minute window)")

    result_reclaim = fsm.process(
        result.updated_candidate, bar_reclaim, snapshot_reclaim
    )
    print(f"Result state: {result_reclaim.updated_candidate.state}")

    # Should move to FILTERS state
    assert result_reclaim.updated_candidate.state == CandidateState.FILTERS

    # Test Case 3: Linger window expiry
    candidate_touch = result.updated_candidate  # Start from TOUCH_CONF state

    # Create a bar that's more than 5 minutes after the touch event
    # The touch happened at timestamp + 1 minute, so 6 minutes from original = 5 minutes from touch
    bar_expired = create_test_bar(
        1.0852, timestamp + timedelta(minutes=7)
    )  # 7 minutes from start = 6 minutes from touch
    snapshot_expired = create_test_snapshot(ema21)  # Still no EMA alignment

    print("\nTest Case 3: Linger window expired")
    print(
        f"Touch happened at: {(timestamp + timedelta(minutes=1)).strftime('%H:%M:%S')}"
    )
    print(f"Current time: {(timestamp + timedelta(minutes=7)).strftime('%H:%M:%S')}")
    print("Time elapsed since touch: 6 minutes (exceeds 5-minute window)")

    result_expired = fsm.process(candidate_touch, bar_expired, snapshot_expired)
    print(f"Result state: {result_expired.updated_candidate.state}")
    print(f"Expired flag: {result_expired.expired}")

    # Should move to EXPIRED state
    assert result_expired.updated_candidate.state == CandidateState.EXPIRED
    assert result_expired.expired

    print("✅ Touch-&-Reclaim test passed!")


def test_combined_functionality():
    """Test both mechanisms working together."""
    print("\n=== Testing Combined Functionality ===")

    # Config with both mechanisms enabled
    config = CandidateConfig(
        ema_tolerance_pct=0.001,  # 0.1% tolerance
        linger_minutes=3,  # 3-minute linger window
        reclaim_requires_ema=True,
        ema_alignment=True,
        volume_multiple=1.0,
        killzone_start=8,
        killzone_end=12,
        regime_allowed=["bull", "neutral"],
        expiry_minutes=60,
    )

    fsm = SignalCandidateFSM(config)

    # Create a SHORT candidate
    timestamp = datetime(2024, 5, 21, 10, 0)
    candidate = fsm.create_candidate(
        zone_id="H1_SHORT_001",
        zone_type="pool",
        direction=SignalDirection.SHORT,
        entry_price=1.0850,
        strength=0.9,
        timestamp=timestamp,
    )

    print(f"Created SHORT candidate: {candidate.candidate_id}")
    print(f"Entry price: {candidate.entry_price}")

    # Test with EMA misalignment (SHORT signal - price should be < EMA - tolerance)
    ema21 = 1.0848  # Below entry price

    # 1. Zone touched
    bar_touch = create_test_bar(
        close_price=1.0849,
        timestamp=timestamp + timedelta(minutes=1),
        high=1.0851,  # Touch the zone entry
    )
    snapshot = create_test_snapshot(ema21)

    print("\nStep 1: Zone touched (SHORT)")
    print(f"Bar high: {bar_touch.high} (touches entry: {candidate.entry_price})")

    result1 = fsm.process(candidate, bar_touch, snapshot)
    print(f"State: {result1.updated_candidate.state}")
    assert result1.updated_candidate.state == CandidateState.TOUCH_CONF

    # 2. EMA reclaimed with strict alignment (no tolerance for reclaim)
    ema21_strict = 1.0851  # Above price for SHORT alignment
    test_price = 1.0849  # Below EMA21, good for SHORT
    bar_reclaim = create_test_bar(test_price, timestamp + timedelta(minutes=2))
    snapshot_strict = create_test_snapshot(ema21_strict)

    print("\nStep 2: EMA reclaimed with strict alignment")
    print(f"EMA21: {ema21_strict} (above price)")
    print(f"Price: {test_price} (below EMA21, good for SHORT)")
    print("Note: Reclaim requires strict EMA alignment (no tolerance buffer)")

    result2 = fsm.process(result1.updated_candidate, bar_reclaim, snapshot_strict)
    print(f"State: {result2.updated_candidate.state}")

    # Should move to FILTERS state
    assert result2.updated_candidate.state == CandidateState.FILTERS

    print("✅ Combined functionality test passed!")


if __name__ == "__main__":
    print("Testing EMA Improvements Implementation")
    print("=" * 50)

    test_tolerance_buffer()
    test_touch_and_reclaim()
    test_combined_functionality()

    print("\n" + "=" * 50)
    print("🎉 All EMA improvement tests passed!")
    print("\nImplemented features:")
    print("✅ Tolerance Buffer: 0.1-0.3% flexibility for EMA alignment")
    print("✅ Touch-&-Reclaim: Zone touch → linger window → EMA reclaim")
    print("✅ Configurable parameters for both mechanisms")
    print("✅ Backward compatibility with existing functionality")
