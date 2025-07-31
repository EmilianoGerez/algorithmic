#!/usr/bin/env python3
"""
Test script for entry spacing mechanism implementation.

Tests the 30-minute per-pool and 10-minute global entry spacing
to prevent rapid-fire trades from causing excessive drawdown.
"""

import logging
from datetime import datetime, timedelta

from core.entities import Candle
from core.indicators.regime import Regime
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.pool_models import LiquidityPool, PoolCreatedEvent, PoolState
from core.strategy.signal_candidate import CandidateConfig
from core.strategy.signal_models import CandidateState, SignalDirection, ZoneType
from core.strategy.zone_watcher import ZoneWatcher, ZoneWatcherConfig

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_pools():
    """Create test liquidity pools for different zones."""
    base_time = datetime(2024, 5, 20, 13, 0)  # In killzone

    pools = []
    for i in range(3):
        pool_id = f"H1_EURUSD_pool_{i:03d}"
        pool = LiquidityPool(
            pool_id=pool_id,
            timeframe="H1",
            state=PoolState.ACTIVE,
            top=1.08500 + (i * 0.00050),  # Spread pools vertically
            bottom=1.08450 + (i * 0.00050),
            strength=3.0,
            created_at=base_time,
            last_touched_at=None,
            expires_at=base_time + timedelta(hours=4),
            hit_tolerance=0.00005,
        )
        pools.append(pool)

    return pools


def create_good_market_snapshot(timestamp: datetime) -> IndicatorSnapshot:
    """Create snapshot that passes all filters."""
    return IndicatorSnapshot(
        timestamp=timestamp,
        ema21=1.08480,
        ema50=1.08470,
        atr=0.00120,
        volume_sma=1000.0,
        regime=Regime.BULL,
        regime_with_slope=Regime.BULL,
        current_volume=1500,
        current_close=1.08495,
    )


def test_basic_entry_spacing():
    """Test basic entry spacing functionality."""
    print("\n🧪 Test 1: Basic Entry Spacing")

    # Configure with entry spacing enabled
    zone_config = ZoneWatcherConfig(
        price_tolerance=0.00005,
        min_strength=1.0,
        enable_spacing_throttle=True,
        min_entry_spacing_minutes=30,
        global_min_entry_spacing=10,
    )

    candidate_config = CandidateConfig(
        expiry_minutes=120,
        ema_alignment=True,
        volume_multiple=1.2,
        killzone_start="12:00",
        killzone_end="15:00",
        regime_allowed=["bull", "neutral"],
    )

    zone_watcher = ZoneWatcher(zone_config, candidate_config)

    # Create test pools
    pools = create_test_pools()
    base_time = datetime(2024, 5, 20, 13, 0)

    # Add pools to zone watcher
    for pool in pools:
        event = PoolCreatedEvent(pool_id=pool.pool_id, timestamp=base_time, pool=pool)
        zone_watcher.on_pool_event(event)

    print(f"✅ Added {len(pools)} pools to zone watcher")

    # Test price entering first pool multiple times
    entry_price = 1.08475  # Hits pool_000
    candle1 = Candle(
        ts=base_time,
        open=1.08470,
        high=1.08490,
        low=1.08460,
        close=entry_price,
        volume=1500,
    )

    # First entry should be allowed
    zone_events = zone_watcher.on_price_update(candle1)
    print(f"First entry: {len(zone_events)} zone events generated")

    if zone_events:
        candidate1 = zone_watcher.spawn_candidate(zone_events[0], base_time)
        print(f"First candidate created: {candidate1 is not None}")

        # Process through FSM to READY state
        snapshot = create_good_market_snapshot(base_time)

        # Simulate FSM processing by calling ready callback directly
        # (In real usage, this would happen through FSM.process())
        zone_watcher.record_candidate_ready(zone_events[0].zone_id, base_time)
        print("✅ First candidate processed to READY state")

    # Second entry 10 minutes later (should be throttled by per-pool spacing)
    candle2 = Candle(
        ts=base_time + timedelta(minutes=10),
        open=1.08470,
        high=1.08490,
        low=1.08460,
        close=entry_price,
        volume=1500,
    )

    # Simulate new zone entry by manually calling spawn_candidate
    from core.strategy.signal_models import ZoneEnteredEvent

    manual_zone_event = ZoneEnteredEvent(
        zone_id=pools[0].pool_id,
        zone_type=ZoneType.POOL,
        entry_price=entry_price,
        timestamp=base_time + timedelta(minutes=10),
        timeframe="H1",
        strength=3.0,
        side="bullish",
    )

    candidate2 = zone_watcher.spawn_candidate(
        manual_zone_event, base_time + timedelta(minutes=10)
    )
    print(
        f"Second candidate (10min later): {candidate2 is not None} (should be False - throttled)"
    )

    # Third entry 35 minutes later (should be allowed)
    candle3 = Candle(
        ts=base_time + timedelta(minutes=35),
        open=1.08470,
        high=1.08490,
        low=1.08460,
        close=entry_price,
        volume=1500,
    )

    manual_zone_event3 = ZoneEnteredEvent(
        zone_id=pools[0].pool_id,
        zone_type=ZoneType.POOL,
        entry_price=entry_price,
        timestamp=base_time + timedelta(minutes=35),
        timeframe="H1",
        strength=3.0,
        side="bullish",
    )

    candidate3 = zone_watcher.spawn_candidate(
        manual_zone_event3, base_time + timedelta(minutes=35)
    )
    print(
        f"Third candidate (35min later): {candidate3 is not None} (should be True - allowed)"
    )

    # Check statistics
    stats = zone_watcher._stats
    print("\n📊 Statistics:")
    print(f"  Candidates spawned: {stats['candidates_spawned']}")
    print(f"  Entries throttled (per-pool): {stats['entries_throttled_per_pool']}")
    print(f"  Entries throttled (global): {stats['entries_throttled_global']}")


def test_global_spacing_different_pools():
    """Test global spacing across different pools."""
    print("\n🧪 Test 2: Global Spacing Across Different Pools")

    zone_config = ZoneWatcherConfig(
        price_tolerance=0.00005,
        min_strength=1.0,
        enable_spacing_throttle=True,
        min_entry_spacing_minutes=30,
        global_min_entry_spacing=10,
    )

    candidate_config = CandidateConfig(
        expiry_minutes=120,
        ema_alignment=True,
        volume_multiple=1.2,
        killzone_start="12:00",
        killzone_end="15:00",
        regime_allowed=["bull", "neutral"],
    )

    zone_watcher = ZoneWatcher(zone_config, candidate_config)

    # Create test pools
    pools = create_test_pools()
    base_time = datetime(2024, 5, 20, 13, 0)

    # Add pools to zone watcher
    for pool in pools:
        event = PoolCreatedEvent(pool_id=pool.pool_id, timestamp=base_time, pool=pool)
        zone_watcher.on_pool_event(event)

    # Entry in pool_000
    candle1 = Candle(
        ts=base_time,
        open=1.08470,
        high=1.08490,
        low=1.08460,
        close=1.08475,  # Hits pool_000
        volume=1500,
    )

    zone_events1 = zone_watcher.on_price_update(candle1)
    if zone_events1:
        candidate1 = zone_watcher.spawn_candidate(zone_events1[0], base_time)
        zone_watcher.record_candidate_ready(zone_events1[0].zone_id, base_time)
        print("✅ First entry in pool_000 processed to READY")

    # Entry in pool_001 5 minutes later (different pool, but global spacing should throttle)
    candle2 = Candle(
        ts=base_time + timedelta(minutes=5),
        open=1.08520,
        high=1.08540,
        low=1.08510,
        close=1.08525,  # Hits pool_001
        volume=1500,
    )

    # Simulate zone entry for pool_001
    from core.strategy.signal_models import ZoneEnteredEvent

    manual_zone_event2 = ZoneEnteredEvent(
        zone_id=pools[1].pool_id,
        zone_type=ZoneType.POOL,
        entry_price=1.08525,
        timestamp=base_time + timedelta(minutes=5),
        timeframe="H1",
        strength=3.0,
        side="bullish",
    )

    candidate2 = zone_watcher.spawn_candidate(
        manual_zone_event2, base_time + timedelta(minutes=5)
    )
    print(
        f"Second entry in pool_001 (5min later): {candidate2 is not None} (should be False - global throttling)"
    )

    # Entry in pool_002 15 minutes later (should be allowed - global spacing passed)
    candle3 = Candle(
        ts=base_time + timedelta(minutes=15),
        open=1.08570,
        high=1.08590,
        low=1.08560,
        close=1.08575,  # Hits pool_002
        volume=1500,
    )

    manual_zone_event3 = ZoneEnteredEvent(
        zone_id=pools[2].pool_id,
        zone_type=ZoneType.POOL,
        entry_price=1.08575,
        timestamp=base_time + timedelta(minutes=15),
        timeframe="H1",
        strength=3.0,
        side="bullish",
    )

    candidate3 = zone_watcher.spawn_candidate(
        manual_zone_event3, base_time + timedelta(minutes=15)
    )
    print(
        f"Third entry in pool_002 (15min later): {candidate3 is not None} (should be True - global spacing OK)"
    )

    # Check statistics
    stats = zone_watcher._stats
    print("\n📊 Statistics:")
    print(f"  Candidates spawned: {stats['candidates_spawned']}")
    print(f"  Entries throttled (per-pool): {stats['entries_throttled_per_pool']}")
    print(f"  Entries throttled (global): {stats['entries_throttled_global']}")


def test_throttling_disabled():
    """Test that throttling can be disabled."""
    print("\n🧪 Test 3: Throttling Disabled")

    zone_config = ZoneWatcherConfig(
        price_tolerance=0.00005,
        min_strength=1.0,
        enable_spacing_throttle=False,  # Disabled
        min_entry_spacing_minutes=30,
        global_min_entry_spacing=10,
    )

    candidate_config = CandidateConfig(
        expiry_minutes=120,
        ema_alignment=True,
        volume_multiple=1.2,
        killzone_start="12:00",
        killzone_end="15:00",
        regime_allowed=["bull", "neutral"],
    )

    zone_watcher = ZoneWatcher(zone_config, candidate_config)

    # Create test pool
    pools = create_test_pools()[:1]  # Just one pool
    base_time = datetime(2024, 5, 20, 13, 0)

    pool = pools[0]
    event = PoolCreatedEvent(pool_id=pool.pool_id, timestamp=base_time, pool=pool)
    zone_watcher.on_pool_event(event)

    # Rapid entries should all be allowed
    entry_times = [0, 1, 2, 5, 10]  # Minutes
    allowed_entries = 0

    from core.strategy.signal_models import ZoneEnteredEvent

    for i, minutes in enumerate(entry_times):
        candle = Candle(
            ts=base_time + timedelta(minutes=minutes),
            open=1.08470,
            high=1.08490,
            low=1.08460,
            close=1.08475,  # Hits pool
            volume=1500,
        )

        # Simulate zone entry manually
        manual_zone_event = ZoneEnteredEvent(
            zone_id=pool.pool_id,
            zone_type=ZoneType.POOL,
            entry_price=1.08475,
            timestamp=base_time + timedelta(minutes=minutes),
            timeframe="H1",
            strength=3.0,
            side="bullish",
        )

        candidate = zone_watcher.spawn_candidate(
            manual_zone_event, base_time + timedelta(minutes=minutes)
        )
        if candidate is not None:
            allowed_entries += 1
            print(f"Entry {i + 1} at {minutes}min: ✅ ALLOWED")
        else:
            print(f"Entry {i + 1} at {minutes}min: ❌ THROTTLED")

    print(
        f"\nWith throttling disabled: {allowed_entries}/{len(entry_times)} entries allowed (should be {len(entry_times)})"
    )


def main():
    """Run all entry spacing tests."""
    print("🚀 Entry Spacing Mechanism Tests")
    print("=" * 50)

    try:
        test_basic_entry_spacing()
        test_global_spacing_different_pools()
        test_throttling_disabled()

        print("\n✅ All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
