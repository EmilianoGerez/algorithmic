"""
Debug test for touch-&-reclaim mechanism with extended expiry.
"""

from datetime import datetime, timedelta

from core.entities import Candle
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.signal_candidate import CandidateConfig, SignalCandidateFSM
from core.strategy.signal_models import CandidateState, SignalDirection


def create_test_bar(
    timestamp: datetime,
    close: float,
    low: float | None = None,
    high: float | None = None,
) -> Candle:
    """Create a simple test bar."""
    return Candle(
        open=close - 0.0001,
        high=high or close + 0.0002,
        low=low or close - 0.0002,
        close=close,
        volume=1000.0,
        ts=timestamp,
    )


def create_snapshot(
    timestamp: datetime, ema21: float, ema50: float | None = None
) -> IndicatorSnapshot:
    """Create indicator snapshot."""
    return IndicatorSnapshot(
        timestamp=timestamp,
        ema21=ema21,
        ema50=ema50 or ema21 - 0.01,
        atr=0.001,
        volume_sma=800.0,
        regime=None,
        regime_with_slope=None,
        current_volume=1000.0,
        current_close=ema21,
    )


def test_touch_reclaim_simple():
    """Simple test of touch-&-reclaim with extended expiry."""

    print("=== Simple Touch-&-Reclaim Test ===")

    # Extended expiry to avoid timing issues
    config = CandidateConfig(
        ema_tolerance_pct=0.0,
        linger_minutes=60,  # 60-minute linger window
        reclaim_requires_ema=True,
        ema_alignment=True,
        volume_multiple=1.0,  # Relaxed volume requirement
        killzone_start="00",  # All-day killzone
        killzone_end="23",
        regime_allowed=["bull", "neutral", "bear"],  # All regimes
        expiry_minutes=1440,  # 24-hour expiry
    )

    fsm = SignalCandidateFSM(config, symbol="BTCUSDT", timeframe="5m")

    # Create candidate at 10:00
    base_time = datetime(2024, 5, 20, 10, 0)
    candidate = fsm.create_candidate(
        zone_id="TEST_FVG_001",
        zone_type="pool",
        direction=SignalDirection.LONG,
        entry_price=1.0850,
        strength=0.8,
        timestamp=base_time,
    )

    print(f"Created candidate at: {base_time}")
    print(f"Expires at: {candidate.expires_at}")
    print(f"Initial state: {candidate.state}")
    print()

    # Step 1: Initial check - no EMA alignment (10:05)
    time1 = base_time + timedelta(minutes=5)
    bar1 = create_test_bar(time1, 1.0852)  # Above FVG
    snap1 = create_snapshot(time1, 1.0860)  # EMA21 above price (no alignment)

    result1 = fsm.process(candidate, bar1, snap1)
    print(f"Step 1 ({time1.strftime('%H:%M')}): No EMA alignment")
    print(f"Price: {bar1.close}, EMA21: {snap1.ema21}")
    print(f"State: {result1.updated_candidate.state}")
    print(f"Expired: {result1.expired}")
    print()

    # Step 2: Zone touched (10:15)
    time2 = base_time + timedelta(minutes=15)
    bar2 = create_test_bar(time2, 1.0851, low=1.0848)  # Low touches FVG at 1.0850
    snap2 = create_snapshot(time2, 1.0855)  # Still no EMA alignment

    result2 = fsm.process(result1.updated_candidate, bar2, snap2)
    print(f"Step 2 ({time2.strftime('%H:%M')}): 🎯 ZONE TOUCHED")
    print(f"Bar low: {bar2.low} (touches FVG: 1.0850)")
    print(f"Price: {bar2.close}, EMA21: {snap2.ema21}")
    print(f"State: {result2.updated_candidate.state}")
    print(f"Expired: {result2.expired}")
    print()

    # Step 3: EMA reclaim (10:45 - within 60-minute window)
    time3 = base_time + timedelta(minutes=45)
    bar3 = create_test_bar(time3, 1.0851)
    snap3 = create_snapshot(time3, 1.0848)  # EMA21 below price (alignment!)

    result3 = fsm.process(result2.updated_candidate, bar3, snap3)
    print(f"Step 3 ({time3.strftime('%H:%M')}): 🚀 EMA RECLAIMED")
    print(f"Price: {bar3.close}, EMA21: {snap3.ema21} (alignment achieved!)")
    print(f"Time since touch: {(time3 - time2).total_seconds() / 60:.0f} minutes")
    print(f"State: {result3.updated_candidate.state}")
    print(f"Expired: {result3.expired}")

    if result3.updated_candidate.state == CandidateState.FILTERS:
        print("✅ SUCCESS! Moved to FILTERS state")

        # Step 4: Check if signal is generated
        result4 = fsm.process(result3.updated_candidate, bar3, snap3)
        if result4.signal:
            print("🎉 TRADING SIGNAL GENERATED!")
            return True
        else:
            print("⚠️ No signal (filters may have failed)")
            return False
    else:
        print("❌ FAILED! Did not reach FILTERS state")
        return False


if __name__ == "__main__":
    success = test_touch_reclaim_simple()

    print("\n" + "=" * 50)
    if success:
        print("🎉 Touch-&-Reclaim mechanism working correctly!")
    else:
        print("❌ Touch-&-Reclaim needs debugging")
