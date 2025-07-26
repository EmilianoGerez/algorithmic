#!/usr/bin/env python3
"""
Demo script showing Phase 1 indicator implementation.

Shows IndicatorPack usage with synthetic data.
"""

from datetime import datetime, timedelta

from core.entities import Candle
from core.indicators import IndicatorPack


def create_demo_candles(count: int = 100) -> list[Candle]:
    """Create demo candles with upward trend."""
    candles = []
    base_price = 100.0
    base_time = datetime(2025, 1, 1, 9, 0)

    for i in range(count):
        # Gradual upward trend with noise
        trend = i * 0.1
        noise = (i % 7 - 3) * 0.2
        price = base_price + trend + noise

        candle = Candle(
            ts=base_time + timedelta(minutes=i),
            open=price - 0.1,
            high=price + 0.3,
            low=price - 0.2,
            close=price,
            volume=1000 + (i % 10) * 100,
        )
        candles.append(candle)

    return candles


def main():
    print("🚀 Phase 1 Indicator Demo")
    print("=" * 50)

    # Initialize indicator pack
    pack = IndicatorPack(
        ema21_period=21,
        ema50_period=50,
        atr_period=14,
        volume_sma_period=20,
        regime_sensitivity=0.001,
    )

    print(f"Warmup periods needed: {pack.warmup_periods_needed}")
    print()

    # Generate demo data
    candles = create_demo_candles(100)
    print(f"Processing {len(candles)} candles...")

    # Process candles and show progress
    for i, candle in enumerate(candles):
        pack.update(candle)

        # Show snapshot every 20 candles once ready
        if pack.is_ready and (i + 1) % 20 == 0:
            snapshot = pack.snapshot()

            print(f"\n📊 Snapshot at candle {i + 1} ({snapshot.timestamp})")
            print(f"  Close: ${snapshot.current_close:.2f}")
            print(f"  EMA21: ${snapshot.ema21:.2f}")
            print(f"  EMA50: ${snapshot.ema50:.2f}")
            print(f"  ATR: ${snapshot.atr:.3f}")
            print(f"  Volume SMA: {snapshot.volume_sma:.0f}")
            print(f"  Volume Multiple: {snapshot.volume_multiple:.2f}x")
            print(f"  Regime: {snapshot.regime.name}")
            print(f"  Regime (slope): {snapshot.regime_with_slope.name}")
            print(
                f"  EMA Aligned: {'🟢 Bullish' if snapshot.ema_aligned_bullish else '🔴 Bearish' if snapshot.ema_aligned_bearish else '🟡 Neutral'}"
            )

    # Final summary
    final_snapshot = pack.snapshot()
    print("\n🎯 Final Results")
    print(f"  Total candles processed: {len(candles)}")
    print(f"  Final regime: {final_snapshot.regime.name}")
    print(f"  EMA21 > EMA50: {final_snapshot.ema_aligned_bullish}")
    print(f"  All indicators ready: {final_snapshot.is_ready}")

    print("\n✅ Phase 1 implementation complete!")
    print("Ready for Phase 2: TimeAggregator")


if __name__ == "__main__":
    main()
