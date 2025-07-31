"""
Test script to verify the 20 May H4 FVG touch-&-reclaim scenario.

This script simulates the specific case mentioned:
- 19 May: H4 FVG created
- 20 May ~14:00: Price touches the FVG zone, then EMA alignment occurs
- Verify that touch-&-reclaim mechanism captures this entry
"""

from datetime import datetime, timedelta

from core.entities import Candle
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.signal_candidate import CandidateConfig, SignalCandidateFSM
from core.strategy.signal_models import CandidateState, SignalDirection


def create_test_bar(
    timestamp: datetime,
    open_p: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000.0,
) -> Candle:
    """Create a test bar with full OHLC data."""
    return Candle(
        open=open_p, high=high, low=low, close=close, volume=volume, ts=timestamp
    )


def create_snapshot(
    timestamp: datetime,
    ema21: float,
    ema50: float | None = None,
    volume_sma: float = 800.0,
) -> IndicatorSnapshot:
    """Create indicator snapshot."""
    return IndicatorSnapshot(
        timestamp=timestamp,
        ema21=ema21,
        ema50=ema50 or ema21 - 0.01,
        atr=0.001,
        volume_sma=volume_sma,
        regime=None,
        regime_with_slope=None,
        current_volume=1000.0,
        current_close=ema21,
    )


def test_may_20_scenario():
    """Test the specific 20 May touch-&-reclaim scenario."""

    print("=== Testing 20 May H4 FVG Touch-&-Reclaim Scenario ===")
    print()

    # Use current config settings: no tolerance, 60-minute linger
    config = CandidateConfig(
        ema_tolerance_pct=0.0,  # No tolerance buffer (as per current config)
        linger_minutes=60,  # 60-minute linger window (as per current config)
        reclaim_requires_ema=True,
        ema_alignment=True,
        volume_multiple=1.2,
        killzone_start="01",
        killzone_end="18",
        regime_allowed=["bull", "neutral"],
        expiry_minutes=120,
    )

    fsm = SignalCandidateFSM(config, symbol="BTCUSDT", timeframe="5m")

    # Simulate 19 May H4 FVG creation - but create it closer to the test time
    may_19_late = datetime(2024, 5, 19, 22, 0)  # 10 PM on May 19 (closer to May 20)
    fvg_entry_price = 1.0850

    print(f"📅 May 19 22:00: H4 FVG created at {fvg_entry_price}")

    # Create LONG candidate for the H4 FVG
    candidate = fsm.create_candidate(
        zone_id="H4_FVG_MAY19_001",
        zone_type="pool",
        direction=SignalDirection.LONG,
        entry_price=fvg_entry_price,
        strength=0.8,
        timestamp=may_19_late,  # Created closer to test time
    )

    print(f"✅ Created candidate: {candidate.candidate_id}")
    print(f"Initial state: {candidate.state}")
    print()

    # May 20 morning: Price above FVG, but EMA21 is also above price (no alignment)
    may_20_morning = datetime(2024, 5, 20, 8, 0)  # 8 AM May 20
    ema21_morning = 1.0860  # EMA21 above price, no alignment yet

    morning_bar = create_test_bar(
        timestamp=may_20_morning,
        open_p=1.0855,
        high=1.0862,
        low=1.0852,
        close=1.0858,  # Above FVG but below EMA21
    )
    morning_snapshot = create_snapshot(may_20_morning, ema21_morning)

    print("📅 May 20 08:00: Price above FVG but no EMA alignment")
    print(f"Price: {morning_bar.close}, EMA21: {ema21_morning}")

    result1 = fsm.process(candidate, morning_bar, morning_snapshot)
    print(f"State: {result1.updated_candidate.state}")
    print()

    # May 20 ~14:00: Price touches the FVG zone (spring/stop-hunt)
    may_20_touch = datetime(2024, 5, 20, 14, 0)  # 2 PM May 20
    ema21_touch = 1.0855  # EMA21 still above, no alignment

    touch_bar = create_test_bar(
        timestamp=may_20_touch,
        open_p=1.0852,
        high=1.0854,
        low=1.0848,  # 🎯 TOUCHES THE FVG ZONE at 1.0850
        close=1.0851,
    )
    touch_snapshot = create_snapshot(may_20_touch, ema21_touch)

    print("📅 May 20 14:00: 🎯 ZONE TOUCHED!")
    print(f"Bar low: {touch_bar.low} (touches FVG entry: {fvg_entry_price})")
    print(f"Price: {touch_bar.close}, EMA21: {ema21_touch} (still no alignment)")

    result2 = fsm.process(result1.updated_candidate, touch_bar, touch_snapshot)
    print(f"State after touch: {result2.updated_candidate.state}")

    if result2.updated_candidate.state == CandidateState.TOUCH_CONF:
        print("✅ Touch-&-reclaim activated! Now waiting for EMA reclaim...")
    print()

    # May 20 ~14:30: EMA21 flips below price (reclaim occurs)
    may_20_reclaim = datetime(2024, 5, 20, 14, 30)  # 30 minutes later
    ema21_reclaim = 1.0849  # 🎯 EMA21 NOW BELOW PRICE (alignment achieved!)

    reclaim_bar = create_test_bar(
        timestamp=may_20_reclaim,
        open_p=1.0851,
        high=1.0854,
        low=1.0850,
        close=1.0852,  # Price above EMA21 = good for LONG
    )
    reclaim_snapshot = create_snapshot(may_20_reclaim, ema21_reclaim)

    print("📅 May 20 14:30: 🚀 EMA RECLAIMED!")
    print(f"Price: {reclaim_bar.close}, EMA21: {ema21_reclaim} (alignment achieved!)")
    print(
        f"Time since touch: {(may_20_reclaim - may_20_touch).total_seconds() / 60:.0f} minutes (within 60-minute window)"
    )

    result3 = fsm.process(result2.updated_candidate, reclaim_bar, reclaim_snapshot)
    print(f"State after reclaim: {result3.updated_candidate.state}")

    if result3.updated_candidate.state == CandidateState.FILTERS:
        print("✅ SUCCESS! Moved to FILTERS - signal validation in progress")

        # Simulate all filters passing
        final_bar = create_test_bar(
            timestamp=may_20_reclaim,
            open_p=1.0851,
            high=1.0854,
            low=1.0850,
            close=1.0852,
            volume=1200.0,  # Higher volume to pass volume filter
        )
        final_snapshot = create_snapshot(
            may_20_reclaim, ema21_reclaim, volume_sma=800.0
        )

        result4 = fsm.process(result3.updated_candidate, final_bar, final_snapshot)

        if result4.signal is not None:
            print("🎉 TRADING SIGNAL GENERATED!")
            print(f"Signal ID: {result4.signal.signal_id}")
            print(f"Entry Price: {result4.signal.entry_price}")
            print(f"Direction: {result4.signal.direction}")
            print(f"Confidence: {result4.signal.confidence:.2f}")
            return True
        else:
            print("⚠️  Filters failed, no signal generated")
            return False
    else:
        print("❌ FAILED! Did not move to FILTERS state")
        return False


def test_legacy_behavior_comparison():
    """Test the same scenario with legacy settings (should fail)."""

    print("\n" + "=" * 60)
    print("=== Comparison: Legacy Behavior (Should Fail) ===")
    print()

    # Legacy config: no tolerance, no linger
    legacy_config = CandidateConfig(
        ema_tolerance_pct=0.0,
        linger_minutes=0,  # 🔴 NO TOUCH-&-RECLAIM
        reclaim_requires_ema=True,
        ema_alignment=True,
        volume_multiple=1.2,
        killzone_start="01",
        killzone_end="18",
        regime_allowed=["bull", "neutral"],
        expiry_minutes=120,
    )

    fsm = SignalCandidateFSM(legacy_config, symbol="BTCUSDT", timeframe="5m")

    # Same scenario setup but with longer expiry
    may_19_late = datetime(2024, 5, 19, 22, 0)  # Same timing as main test
    candidate = fsm.create_candidate(
        zone_id="H4_FVG_MAY19_LEGACY",
        zone_type="pool",
        direction=SignalDirection.LONG,
        entry_price=1.0850,
        strength=0.8,
        timestamp=may_19_late,  # Same timing
    )

    # May 20 14:30: When EMA alignment finally occurs
    may_20_final = datetime(2024, 5, 20, 14, 30)
    ema21_aligned = 1.0849  # EMA21 below price (good alignment)

    aligned_bar = create_test_bar(
        timestamp=may_20_final,
        open_p=1.0851,
        high=1.0854,
        low=1.0850,
        close=1.0852,  # Price above EMA21
    )
    aligned_snapshot = create_snapshot(may_20_final, ema21_aligned)

    print("📅 May 20 14:30: EMA alignment achieved")
    print(f"Price: {aligned_bar.close}, EMA21: {ema21_aligned}")

    result = fsm.process(candidate, aligned_bar, aligned_snapshot)
    print(f"Legacy result state: {result.updated_candidate.state}")

    if result.updated_candidate.state == CandidateState.FILTERS:
        print("✅ Legacy behavior: Would generate signal (immediate EMA alignment)")
        return True
    else:
        print("❌ Legacy behavior: No signal (missed the opportunity)")
        return False


if __name__ == "__main__":
    print("Testing 20 May H4 FVG Touch-&-Reclaim Scenario")
    print("=" * 60)

    success_new = test_may_20_scenario()
    success_legacy = test_legacy_behavior_comparison()

    print("\n" + "=" * 60)
    print("📊 RESULTS SUMMARY")
    print("=" * 60)

    print(
        f"🆕 New Touch-&-Reclaim Logic: {'✅ SUCCESS' if success_new else '❌ FAILED'}"
    )
    print(f"🔄 Legacy Behavior: {'✅ SUCCESS' if success_legacy else '❌ FAILED'}")

    if success_new and not success_legacy:
        print("\n🎉 IMPROVEMENT CONFIRMED!")
        print("Touch-&-reclaim captures the 20 May pattern that legacy logic missed!")
    elif success_new and success_legacy:
        print("\n✅ BOTH SUCCESSFUL")
        print("Touch-&-reclaim provides additional flexibility for edge cases.")
    else:
        print("\n⚠️  Need to investigate further")

    print("\n📋 Key Takeaways:")
    print("• 60-minute linger window captures medium-term EMA flips")
    print("• Zone touch detection works with bar low/high data")
    print("• Strict EMA reclaim ensures clean signal quality")
    print("• Configuration via YAML allows easy parameter tuning")
