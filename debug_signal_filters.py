"""
Debug script to understand why the May 20 signal was filtered out despite valid conditions.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def debug_signal_filtering():
    """Debug why the May 20 signal was not generated."""

    print("🐛 SIGNAL FILTERING DEBUG")
    print("=" * 40)

    # Load data
    df = pd.read_csv("data/BTC_USD_5min_20250728_021825.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    # Calculate all indicators
    df["ema21"] = df["close"].ewm(span=21).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["atr"] = df["high"].rolling(14).max() - df["low"].rolling(14).min()
    df["volume_sma"] = df["volume"].rolling(20).mean()

    # Focus on May 20, 16:00 signal
    signal_time = pd.Timestamp("2025-05-20 16:00:00+00:00")
    entry_level = 105716.49

    # Get the signal bar
    signal_bar = df[df["timestamp"] == signal_time]
    if len(signal_bar) == 0:
        print(f"❌ Could not find bar at {signal_time}")
        return

    signal_bar = signal_bar.iloc[0]

    print(f"🎯 Signal Time: {signal_time}")
    print(f"💰 Entry Level: ${entry_level:.2f}")
    print("📊 Signal Bar Data:")
    print(f"   Price: ${signal_bar['close']:.2f}")
    print(f"   EMA21: ${signal_bar['ema21']:.2f}")
    print(f"   EMA50: ${signal_bar['ema50']:.2f}")
    print(f"   Volume: {signal_bar['volume']:.0f}")
    print(f"   Volume SMA: {signal_bar['volume_sma']:.0f}")
    print()

    # Check each filter from base.yaml
    print("🔍 FILTER ANALYSIS")
    print("-" * 30)

    # 1. EMA Alignment Filter
    ema_aligned = signal_bar["close"] > signal_bar["ema21"]
    print(f"1. EMA Alignment: {'✅ PASS' if ema_aligned else '❌ FAIL'}")
    print(f"   Price ({signal_bar['close']:.2f}) > EMA21 ({signal_bar['ema21']:.2f})")

    # 2. EMA Tolerance (currently 0% in config)
    ema_tolerance_pct = 0.0  # From base.yaml
    tolerance = signal_bar["ema21"] * (ema_tolerance_pct / 100)
    ema_tolerance_ok = signal_bar["close"] > (signal_bar["ema21"] - tolerance)
    print(f"2. EMA Tolerance: {'✅ PASS' if ema_tolerance_ok else '❌ FAIL'}")
    print(f"   Tolerance: {ema_tolerance_pct}% = ${tolerance:.2f}")

    # 3. Volume Filter
    volume_multiple = 1.2  # From base.yaml
    volume_ok = signal_bar["volume"] > (signal_bar["volume_sma"] * volume_multiple)
    print(f"3. Volume Filter: {'✅ PASS' if volume_ok else '❌ FAIL'}")
    print(
        f"   Volume ({signal_bar['volume']:.0f}) > SMA*{volume_multiple} ({signal_bar['volume_sma'] * volume_multiple:.0f})"
    )

    # 4. Time-based Killzone Filter
    signal_hour = signal_time.hour
    killzone_start = 1  # 01:00
    killzone_end = 18  # 18:00

    # Convert to local time if needed (assuming UTC data)
    in_killzone = killzone_start <= signal_hour <= killzone_end
    print(f"4. Killzone Filter: {'✅ PASS' if in_killzone else '❌ FAIL'}")
    print(
        f"   Signal at {signal_hour:02d}:00, Killzone: {killzone_start:02d}:00-{killzone_end:02d}:00"
    )

    # 5. Market Regime Filter
    # Calculate regime (simplified - based on EMA50 slope)
    prev_idx = df[df["timestamp"] < signal_time].index
    if len(prev_idx) >= 5:
        recent_ema50 = df.loc[prev_idx[-5:], "ema50"].values
        ema50_slope = (recent_ema50[-1] - recent_ema50[0]) / len(recent_ema50)

        if ema50_slope > 50:  # Strong uptrend
            regime = "bull"
        elif ema50_slope < -50:  # Strong downtrend
            regime = "bear"
        else:
            regime = "neutral"
    else:
        regime = "neutral"

    allowed_regimes = ["bull", "neutral"]  # From base.yaml
    regime_ok = regime in allowed_regimes
    print(f"5. Regime Filter: {'✅ PASS' if regime_ok else '❌ FAIL'}")
    print(f"   Current regime: {regime}, Allowed: {allowed_regimes}")

    # 6. FVG Detection Quality
    # Check if this FVG meets detection criteria
    print("\n6. FVG Quality Check:")

    # Need to reconstruct H4 data to check FVG gap size
    df_h4 = (
        df.set_index("timestamp")
        .resample("4h")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )

    # Find the H4 bar that created this FVG
    h4_bar_time = signal_time.floor("4h")
    h4_bars_around = df_h4.loc[
        h4_bar_time - timedelta(hours=8) : h4_bar_time + timedelta(hours=4)
    ]

    if len(h4_bars_around) >= 3:
        # Get the 3-bar pattern
        bars = h4_bars_around.iloc[-3:]
        bar1, bar2, bar3 = bars.iloc[0], bars.iloc[1], bars.iloc[2]

        # Check bullish FVG conditions
        gap_exists = bar1["high"] < bar3["low"]
        gap_size = bar3["low"] - bar1["high"] if gap_exists else 0
        gap_pct = (gap_size / bar2["close"]) * 100 if gap_exists else 0

        # ATR check
        h4_atr = (
            (h4_bars_around["high"] - h4_bars_around["low"]).rolling(14).mean().iloc[-1]
        )
        min_gap_atr = 0.3  # From base.yaml
        atr_ok = gap_size > (h4_atr * min_gap_atr)

        # Percentage check
        min_gap_pct = 0.05  # From base.yaml (0.05%)
        pct_ok = gap_pct > min_gap_pct

        print(f"   Gap size: ${gap_size:.2f} ({gap_pct:.3f}%)")
        print(f"   H4 ATR: ${h4_atr:.2f}, Min gap: ${h4_atr * min_gap_atr:.2f}")
        print(f"   ATR check: {'✅ PASS' if atr_ok else '❌ FAIL'}")
        print(f"   Percentage check: {'✅ PASS' if pct_ok else '❌ FAIL'}")

        fvg_quality_ok = gap_exists and atr_ok and pct_ok
        print(f"   Overall FVG quality: {'✅ PASS' if fvg_quality_ok else '❌ FAIL'}")
    else:
        print("   ❌ Insufficient H4 data for FVG analysis")
        fvg_quality_ok = False

    # Summary
    print("\n" + "=" * 40)
    print("📋 FILTER SUMMARY")
    print("=" * 40)

    all_filters = [
        ("EMA Alignment", ema_aligned),
        ("EMA Tolerance", ema_tolerance_ok),
        ("Volume", volume_ok),
        ("Killzone", in_killzone),
        ("Regime", regime_ok),
        ("FVG Quality", fvg_quality_ok),
    ]

    passed_filters = sum(1 for _, passed in all_filters if passed)

    for name, passed in all_filters:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:15} | {status}")

    print(f"\nFilters passed: {passed_filters}/{len(all_filters)}")

    if passed_filters == len(all_filters):
        print("🎉 ALL FILTERS PASSED - Signal should have been generated!")
        print("💡 Check strategy logic implementation for bugs")
    else:
        failed_filters = [name for name, passed in all_filters if not passed]
        print(f"❌ Failed filters: {', '.join(failed_filters)}")
        print("💡 These are the reasons why no signal was generated")


if __name__ == "__main__":
    debug_signal_filtering()
