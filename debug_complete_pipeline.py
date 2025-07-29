#!/usr/bin/env python3
"""Debug the complete HTF pipeline: FVG creation → Pool creation → Zone touch → Signal generation."""

from datetime import UTC, datetime, timedelta, timezone

import pandas as pd

from core.detectors.fvg import FVGDetector
from core.entities import Candle
from core.indicators.pack import IndicatorPack
from core.strategy.aggregator import TimeAggregator
from core.strategy.pool_manager import PoolManager, PoolManagerConfig
from core.strategy.pool_registry import PoolRegistry, PoolRegistryConfig
from core.strategy.signal_candidate import CandidateConfig, SignalCandidateFSM
from core.strategy.zone_watcher import ZoneWatcher, ZoneWatcherConfig


def debug_complete_pipeline():
    """Debug the complete HTF pipeline from FVG detection to signal generation."""
    print("=== Complete HTF Pipeline Debug ===")

    # Load the actual data
    df = pd.read_csv("data/BTCUSDT_5m_may19-20_fvg_analysis.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"Loaded {len(df)} 5-minute candles")
    
    # Set up simulation clock for backtesting
    from core.clock import use_simulation_clock
    start_time = df['timestamp'].iloc[0].to_pydatetime().replace(tzinfo=UTC)
    sim_clock = use_simulation_clock(start_time)
    print(f"Simulation clock initialized at: {start_time}")

    # Initialize components
    print("\n=== 1. INITIALIZING COMPONENTS ===")

    # H4 Aggregator
    h4_aggregator = TimeAggregator(tf_minutes=240, source_tf_minutes=5)
    print("✅ H4 TimeAggregator initialized")

    # FVG Detector
    fvg_detector = FVGDetector("240", min_gap_atr=0.05, min_gap_pct=0.01, min_rel_vol=0.0)
    print("✅ FVG Detector initialized")

    # Pool Registry & Manager
    registry_config = PoolRegistryConfig(max_pools_per_tf=10000)
    pool_registry = PoolRegistry(registry_config)

    manager_config = PoolManagerConfig(
        ttl_by_timeframe={"240": timedelta(days=3)},  # Use "240" key to match timeframe
        hit_tolerance_by_timeframe={"240": 0.0},
        strength_threshold=0.02  # Lower threshold to capture more FVGs
    )
    pool_manager = PoolManager(pool_registry, manager_config)
    print("✅ Pool Registry & Manager initialized")

    # Zone Watcher
    zone_config = ZoneWatcherConfig(
        price_tolerance=0.0,
        confirm_closure=False,
        min_strength=1.0,
        max_active_zones=1000
    )

    candidate_config = CandidateConfig(
        expiry_minutes=120,
        ema_alignment=True,
        volume_multiple=1.5,
        killzone_start="01:00",
        killzone_end="18:00",
        regime_allowed=["bull", "neutral", "bear"]
    )

    zone_watcher = ZoneWatcher(zone_config, candidate_config)
    print("✅ Zone Watcher initialized")

    # Wire pool manager to zone watcher
    pool_manager.zone_watcher = zone_watcher
    print("✅ Components wired together")

    # Indicators for EMA tracking
    indicators = IndicatorPack()
    print("✅ Indicators initialized")

    # Convert to Candle objects and track key events
    candles = []
    h4_candles = []
    fvg_events = []
    pools_created = []
    zone_touches = []
    signal_candidates = []

    print(f"\n=== 2. PROCESSING {len(df)} 5-MINUTE CANDLES ===")

    for i, row in df.iterrows():
        # Create 5-minute candle
        candle = Candle(
            ts=row['timestamp'].tz_localize(UTC) if row['timestamp'].tz is None else row['timestamp'],
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=row['volume']
        )
        candles.append(candle)
        
        # Advance simulation clock to candle time
        try:
            sim_clock.advance(candle.ts)
        except ValueError:
            pass  # Skip backwards time moves

        # Update indicators
        indicators.update(candle)

        # Aggregate to H4
        completed_h4s = h4_aggregator.update(candle)

        for h4_candle in completed_h4s:
            h4_candles.append(h4_candle)
            print(f"\n📊 H4 Candle Completed: {h4_candle.ts}")
            print(f"   OHLCV: {h4_candle.open:.2f}/{h4_candle.high:.2f}/{h4_candle.low:.2f}/{h4_candle.close:.2f}/{h4_candle.volume:.0f}")

            # Run FVG detection
            atr_value = 1000.0  # Large enough to not block detection
            vol_sma_value = 1000.0  # Not used since min_rel_vol=0.0

            new_fvg_events = fvg_detector.update(h4_candle, atr_value, vol_sma_value)
            fvg_events.extend(new_fvg_events)

            for fvg_event in new_fvg_events:
                print(f"   🎯 FVG DETECTED: {fvg_event.side} [{fvg_event.bottom:.2f}, {fvg_event.top:.2f}] strength={fvg_event.strength:.3f}")

                # Process through pool manager
                result = pool_manager.process_detector_event(fvg_event)
                if result.success and result.pool_created:
                    pools_created.append(result.pool_id)
                    print(f"   ✅ POOL CREATED: {result.pool_id}")

                    # Get the created pool
                    pool = pool_registry.get_pool(result.pool_id)
                    if pool:
                        print(f"      Pool details: TF={pool.timeframe} [{pool.bottom:.2f}, {pool.top:.2f}] strength={pool.strength:.3f}")
                else:
                    print(f"   ❌ POOL CREATION FAILED: {result.reason if hasattr(result, 'reason') else 'Unknown'}")

        # Check for zone touches on every 5-minute candle
        if pools_created:  # Only check if we have pools
            # Check if current price touches any pools
            current_price = candle.close

            for pool_id in pools_created:
                pool = pool_registry.get_pool(pool_id)
                if pool and pool.bottom <= current_price <= pool.top:
                    zone_touches.append((candle.ts, pool_id, current_price))
                    print(f"   🎯 ZONE TOUCH: {candle.ts} price={current_price:.2f} in pool {pool_id} [{pool.bottom:.2f}, {pool.top:.2f}]")

                    # Check EMA alignment for signal generation
                    ema21 = indicators.ema21.value
                    ema50 = indicators.ema50.value

                    if ema21 is not None and ema50 is not None:
                        print(f"      EMA21={ema21:.2f}, EMA50={ema50:.2f}, Close={candle.close:.2f}")

                        # Check if close is above EMA21 (bullish signal condition)
                        if pool.timeframe == "240" and candle.close > ema21:
                            print(f"      ✅ BULLISH SIGNAL CONDITION: Close {candle.close:.2f} > EMA21 {ema21:.2f}")

                            # Check killzone
                            hour = candle.ts.hour
                            in_killzone = 1 <= hour <= 18  # 01:00 to 18:00
                            print(f"      Killzone check: {hour}:00 in_killzone={in_killzone}")

                            if in_killzone:
                                print("      ✅ IN KILLZONE - Signal candidate viable")
                                signal_candidates.append((candle.ts, pool_id, "bullish"))
                            else:
                                print("      ❌ OUTSIDE KILLZONE - Signal rejected")
                        else:
                            print(f"      ❌ BEARISH CONDITION: Close {candle.close:.2f} <= EMA21 {ema21:.2f}")
                    else:
                        print(f"      ⚠️  EMAs not ready: EMA21={ema21}, EMA50={ema50}")

    print("\n=== 3. PIPELINE SUMMARY ===")
    print(f"5-minute candles processed: {len(candles)}")
    print(f"H4 candles generated: {len(h4_candles)}")
    print(f"FVG events detected: {len(fvg_events)}")
    print(f"Pools created: {len(pools_created)}")
    print(f"Zone touches: {len(zone_touches)}")
    print(f"Signal candidates: {len(signal_candidates)}")

    if fvg_events:
        print("\n=== 4. FVG EVENTS DETAILS ===")
        for i, event in enumerate(fvg_events):
            print(f"{i+1}. {event.ts} {event.side} [{event.bottom:.2f}, {event.top:.2f}] strength={event.strength:.3f}")

    if zone_touches:
        print("\n=== 5. ZONE TOUCHES DETAILS ===")
        for i, (ts, pool_id, price) in enumerate(zone_touches):
            print(f"{i+1}. {ts} price={price:.2f} pool={pool_id}")

    if signal_candidates:
        print("\n=== 6. SIGNAL CANDIDATES ===")
        for i, (ts, pool_id, direction) in enumerate(signal_candidates):
            print(f"{i+1}. {ts} {direction} signal from pool {pool_id}")
    else:
        print("\n=== 6. NO SIGNAL CANDIDATES GENERATED ===")
        print("This indicates issues in:")
        print("- Zone touch detection")
        print("- EMA alignment conditions")
        print("- Killzone filtering")
        print("- Signal candidate FSM")

    # Focus on May 20 14:00 area
    print("\n=== 7. MAY 20 14:00 FOCUS ANALYSIS ===")
    may20_14h = datetime(2024, 5, 20, 14, 0, tzinfo=UTC)
    target_candles = [c for c in candles if abs((c.ts - may20_14h).total_seconds()) < 3600]  # ±1 hour

    if target_candles:
        print(f"Candles around May 20 14:00 (±1h): {len(target_candles)}")
        for candle in target_candles[:5]:  # Show first 5
            print(f"  {candle.ts} OHLC: {candle.open:.2f}/{candle.high:.2f}/{candle.low:.2f}/{candle.close:.2f}")

            # Check if this candle touches any FVG pools
            for pool_id in pools_created:
                pool = pool_registry.get_pool(pool_id)
                if pool and pool.bottom <= candle.close <= pool.top:
                    print(f"    🎯 TOUCHES POOL {pool_id}: [{pool.bottom:.2f}, {pool.top:.2f}]")

if __name__ == "__main__":
    debug_complete_pipeline()
