"""
Detailed analysis of the May 20, 16:00 FVG that should have generated an entry.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def detailed_may_20_analysis():
    """Analyze the specific May 20, 16:00 FVG in detail."""

    print("🔍 DETAILED MAY 20 ANALYSIS")
    print("=" * 50)

    # Load data
    df = pd.read_csv("data/BTC_USD_5min_20250728_021825.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    # Calculate EMAs
    df["ema21"] = df["close"].ewm(span=21).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()

    # Focus on May 20, 16:00 FVG (Bullish, Entry: $105716.49)
    fvg_time = pd.Timestamp("2025-05-20 16:00:00+00:00")
    entry_level = 105716.49

    print(f"🎯 Analyzing FVG created at: {fvg_time}")
    print(f"💰 Entry level: ${entry_level:.2f}")
    print("📊 Type: BULLISH (looking for price > EMA21 after zone touch)")
    print()

    # Get the 4-hour window after FVG creation
    end_time = fvg_time + timedelta(hours=4)
    analysis_window = df[
        (df["timestamp"] >= fvg_time) & (df["timestamp"] <= end_time)
    ].copy()

    if len(analysis_window) == 0:
        print("❌ No data in analysis window")
        return

    print(f"📈 Analyzing {len(analysis_window)} bars (4-hour window)")
    print("-" * 50)

    # Track zone touches and EMA alignment
    touches = []
    alignments = []

    for _, bar in analysis_window.iterrows():
        timestamp = bar["timestamp"]
        price = bar["close"]
        low = bar["low"]
        ema21 = bar["ema21"]

        minutes_elapsed = (timestamp - fvg_time).total_seconds() / 60

        # Check if zone was touched (price came down to entry level)
        zone_touched = low <= entry_level

        # Check EMA alignment (for bullish: price > EMA21)
        ema_aligned = price > ema21

        # Track state
        if zone_touched and not any(t["touched"] for t in touches):
            touches.append(
                {
                    "time": timestamp,
                    "minutes": minutes_elapsed,
                    "touched": True,
                    "price": price,
                    "ema21": ema21,
                    "aligned": ema_aligned,
                }
            )
            print(
                f"🎯 ZONE TOUCHED at {timestamp.strftime('%H:%M')} "
                f"(+{minutes_elapsed:.0f}min)"
            )
            print(
                f"   Price: ${price:.2f} | EMA21: ${ema21:.2f} | "
                f"Aligned: {'✅' if ema_aligned else '❌'}"
            )

        # After first touch, track EMA alignment
        if touches and ema_aligned and not any(a["aligned"] for a in alignments):
            alignments.append(
                {
                    "time": timestamp,
                    "minutes": minutes_elapsed,
                    "aligned": True,
                    "price": price,
                    "ema21": ema21,
                }
            )
            touch_time = touches[0]["time"]
            linger_duration = (timestamp - touch_time).total_seconds() / 60
            print(
                f"🚀 EMA ALIGNMENT at {timestamp.strftime('%H:%M')} "
                f"(+{linger_duration:.0f}min after touch)"
            )
            print(f"   Price: ${price:.2f} | EMA21: ${ema21:.2f}")

    print("\n" + "=" * 50)
    print("📊 ANALYSIS RESULTS")
    print("=" * 50)

    if not touches:
        print("❌ Zone was NEVER touched in the 4-hour window")
        print("💡 This explains why no entry was generated")

        # Check what was the closest price got to the zone
        min_distance = analysis_window["low"].min()
        closest_approach = entry_level - min_distance
        print(
            f"🎯 Closest approach: ${min_distance:.2f} "
            f"({closest_approach:.2f} points away from zone)"
        )

    elif not alignments:
        touch_time = touches[0]["time"]
        print(f"✅ Zone was touched at {touch_time.strftime('%H:%M')}")
        print("❌ But EMA alignment was NEVER achieved")

        # Check final EMA position
        final_bar = analysis_window.iloc[-1]
        final_gap = final_bar["close"] - final_bar["ema21"]
        print(f"📈 Final price: ${final_bar['close']:.2f}")
        print(f"📊 Final EMA21: ${final_bar['ema21']:.2f}")
        print(f"📏 Gap: ${final_gap:.2f} ({'Above' if final_gap > 0 else 'Below'} EMA)")

        print("\n💡 60-minute linger window was INSUFFICIENT")
        print("   EMA21 never crossed below price level")

    else:
        touch_time = touches[0]["time"]
        alignment_time = alignments[0]["time"]
        linger_duration = (alignment_time - touch_time).total_seconds() / 60

        print(f"✅ Zone touched at {touch_time.strftime('%H:%M')}")
        print(f"✅ EMA alignment at {alignment_time.strftime('%H:%M')}")
        print(f"⏱️  Linger duration: {linger_duration:.0f} minutes")

        if linger_duration <= 60:
            print("✅ 60-minute window WAS sufficient!")
        else:
            print("❌ 60-minute window was INSUFFICIENT")
            recommended = int(linger_duration) + 15
            print(f"💡 Recommended linger: {recommended} minutes")

    # Provide specific recommendations
    print("\n" + "=" * 50)
    print("⚙️  CONFIGURATION RECOMMENDATIONS")
    print("=" * 50)

    if not touches:
        print("🎯 Issue: Zone never touched")
        print("💡 Solution: Check FVG detection parameters")
        print("   • min_gap_atr might be too strict")
        print("   • Consider lowering to 0.2 from 0.3")

    elif not alignments:
        print("🎯 Issue: EMA alignment too slow")
        print("💡 Solutions:")
        print("   1. Increase linger_minutes to 120-180")
        print("   2. Add ema_tolerance_pct (0.1-0.2%) for near-misses")
        print("   3. Consider faster EMA (EMA13 instead of EMA21)")

    else:
        linger_needed = (
            alignments[0]["time"] - touches[0]["time"]
        ).total_seconds() / 60
        recommended = max(90, int(linger_needed) + 30)
        print(f"🎯 Optimal linger_minutes: {recommended}")


if __name__ == "__main__":
    detailed_may_20_analysis()
