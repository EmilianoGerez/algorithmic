"""
Phase 6 Acceptance Test: ZoneWatcher + FSM Integration

Demonstrates the complete flow:
1. Pool/HLZ creation → ZoneWatcher tracking
2. Price entry → ZoneEnteredEvent
3. Candidate spawn → FSM processing
4. Signal generation

This validates the core Phase 6 deliverables work as designed.
"""

from datetime import datetime, timedelta

from core.entities import Candle
from core.indicators.regime import Regime
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.pool_models import LiquidityPool, PoolCreatedEvent, PoolState
from core.strategy.signal_candidate import CandidateConfig, SignalCandidateFSM
from core.strategy.signal_models import CandidateState, SignalDirection
from core.strategy.zone_watcher import ZoneWatcher, ZoneWatcherConfig


def test_phase6_acceptance_complete_flow() -> None:
    """
    Phase 6 Acceptance Test: Complete signal generation flow.

    Covers: ZoneWatcher → zone tracking → price entry → FSM → signal
    """
    print("🚀 Phase 6 Acceptance Test: ZoneWatcher + FSM")

    # Setup
    base_time = datetime(2024, 1, 1, 13, 0)  # In killzone

    # Configure ZoneWatcher
    zone_config = ZoneWatcherConfig(price_tolerance=0.5, min_strength=1.0)

    candidate_config = CandidateConfig(
        expiry_minutes=120,
        ema_alignment=True,
        volume_multiple=1.2,
        killzone_start="12:00",
        killzone_end="14:05",
        regime_allowed=["bull", "neutral"],
    )

    zone_watcher = ZoneWatcher(zone_config, candidate_config)
    fsm = SignalCandidateFSM(candidate_config, symbol="BTCUSDT", timeframe="H1")

    print("✅ ZoneWatcher and FSM initialized")

    # Step 1: Create liquidity pool and add to tracking
    pool = LiquidityPool(
        pool_id="H1_test_2024-01-01T12:00:00_12345678",
        timeframe="H1",
        top=105.0,  # Wider zone to include our test price
        bottom=98.0,
        strength=3.0,
        state=PoolState.ACTIVE,
        created_at=base_time,
        last_touched_at=None,
        expires_at=base_time + timedelta(hours=4),
    )

    pool_event = PoolCreatedEvent(pool_id=pool.pool_id, timestamp=base_time, pool=pool)

    zone_watcher.on_pool_event(pool_event)
    active_zones = zone_watcher.get_active_zones()

    assert len(active_zones) == 1
    print(f"✅ Pool added to tracking: {pool.pool_id}")

    # Step 2: Price enters zone
    entry_candle = Candle(
        ts=base_time + timedelta(minutes=5),
        open=105.0,
        high=105.0,
        low=97.0,
        close=103.0,  # Above EMA21 (102.0) for LONG signal
        volume=1500,
    )

    zone_events = zone_watcher.on_price_update(entry_candle)

    assert len(zone_events) == 1
    zone_entry = zone_events[0]
    assert zone_entry.entry_price == 103.0
    print(f"✅ Zone entry detected: {zone_entry.zone_id} at {zone_entry.entry_price}")

    # Step 3: Spawn candidate from zone entry
    candidate = zone_watcher.spawn_candidate(zone_entry, entry_candle.ts)

    assert candidate.state == CandidateState.WAIT_EMA
    assert candidate.direction == SignalDirection.LONG
    print(f"✅ Candidate spawned: {candidate.candidate_id}, state: {candidate.state}")

    # Step 4: Create good indicator snapshot
    snapshot = IndicatorSnapshot(
        timestamp=entry_candle.ts,
        ema21=102.0,  # Above EMA50, supports long
        ema50=101.0,
        atr=1.5,
        volume_sma=1000.0,  # Volume threshold base
        regime=Regime.BULL,  # Allowed regime
        regime_with_slope=Regime.BULL,
        current_volume=entry_candle.volume,
        current_close=entry_candle.close,
    )

    # Step 5: First FSM processing - WAIT_EMA → FILTERS
    result1 = fsm.process(candidate, entry_candle, snapshot)

    print(f"Debug: Expected FILTERS, got {result1.updated_candidate.state}")
    print(
        f"Debug: EMA21={snapshot.ema21}, EMA50={snapshot.ema50}, Close={entry_candle.close}"
    )
    # Safe comparison handling None values
    ema21_ok = snapshot.ema21 is not None and entry_candle.close > snapshot.ema21
    ema50_ok = (
        snapshot.ema21 is not None
        and snapshot.ema50 is not None
        and snapshot.ema21 > snapshot.ema50
    )
    print(
        f"Debug: EMA alignment check: close > ema21? {ema21_ok}, ema21 > ema50? {ema50_ok}"
    )

    assert result1.updated_candidate.state == CandidateState.FILTERS
    assert result1.signal is None
    print("✅ FSM transition: WAIT_EMA → FILTERS")

    # Step 6: Second candle with good conditions
    signal_candle = Candle(
        ts=base_time + timedelta(minutes=6),
        open=100.0,
        high=106.0,
        low=99.0,
        close=104.0,  # Still above EMA
        volume=1400,  # Above volume threshold (1000 * 1.2 = 1200)
    )

    snapshot2 = IndicatorSnapshot(
        timestamp=signal_candle.ts,
        ema21=102.5,
        ema50=101.0,
        atr=1.5,
        volume_sma=1000.0,
        regime=Regime.BULL,
        regime_with_slope=Regime.BULL,
        current_volume=signal_candle.volume,
        current_close=signal_candle.close,
    )

    # Step 7: Second FSM processing - FILTERS → READY (with signal!)
    result2 = fsm.process(result1.updated_candidate, signal_candle, snapshot2)

    assert result2.updated_candidate.state == CandidateState.READY
    assert result2.signal is not None

    signal = result2.signal
    assert signal.direction == SignalDirection.LONG
    assert signal.zone_id == pool.pool_id
    assert signal.current_price == 104.0
    assert signal.strength == 3.0
    assert signal.timeframe == "H1"

    print("✅ TRADING SIGNAL GENERATED!")
    print(f"   Signal ID: {signal.signal_id}")
    print(f"   Direction: {signal.direction.value}")
    print(f"   Entry Price: {signal.entry_price}")
    print(f"   Current Price: {signal.current_price}")
    print(f"   Strength: {signal.strength}")
    print(f"   Confidence: {signal.confidence:.2f}")

    # Step 8: Verify statistics
    watcher_stats = zone_watcher.get_stats()
    assert watcher_stats["zones_tracked"] == 1
    assert watcher_stats["zone_entries"] == 1
    assert watcher_stats["candidates_spawned"] == 1

    print(f"✅ Statistics verified: {watcher_stats}")

    print("\n🎉 Phase 6 Acceptance Test PASSED!")
    print("   ✓ ZoneWatcher tracks pools/HLZs")
    print("   ✓ Price entry detection works")
    print("   ✓ Candidate spawning works")
    print("   ✓ FSM state transitions work")
    print("   ✓ Signal generation works")
    print("   ✓ All components integrate correctly")


if __name__ == "__main__":
    test_phase6_acceptance_complete_flow()
