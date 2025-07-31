"""
Diagnostic script to trace the entire signal generation pipeline.
This will help identify where in the chain the May 20 signal is being lost.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yaml


def trace_signal_pipeline():
    """Trace the entire signal generation pipeline step by step."""

    print("🔍 SIGNAL PIPELINE DIAGNOSTICS")
    print("=" * 50)

    # Load configuration
    with open("configs/base.yaml") as f:
        config = yaml.safe_load(f)

    # Load data
    df = pd.read_csv("data/BTC_USD_5min_20250728_021825.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    print(
        f"📊 Dataset: {len(df)} rows from {df['timestamp'].min()} to {df['timestamp'].max()}"
    )
    print()

    # Step 1: Check if H4 aggregation works
    print("📈 STEP 1: H4 Aggregation Check")
    print("-" * 30)

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

    print(f"H4 bars created: {len(df_h4)}")
    print("Sample H4 bars:")
    for i in range(min(5, len(df_h4))):
        bar = df_h4.iloc[i]
        print(
            f"  {df_h4.index[i].strftime('%Y-%m-%d %H:%M')} | O:{bar['open']:.2f} H:{bar['high']:.2f} L:{bar['low']:.2f} C:{bar['close']:.2f}"
        )
    print()

    # Step 2: Check FVG detection
    print("🎯 STEP 2: FVG Detection Check")
    print("-" * 30)

    # Simulate FVG detection logic
    fvgs_detected = []
    min_gap_atr = config["detectors"]["fvg"]["min_gap_atr"]
    min_gap_pct = config["detectors"]["fvg"]["min_gap_pct"]
    min_rel_vol = config["detectors"]["fvg"]["min_rel_vol"]

    print(
        f"FVG thresholds: min_gap_atr={min_gap_atr}, min_gap_pct={min_gap_pct}, min_rel_vol={min_rel_vol}"
    )

    # Calculate H4 ATR for quality checks
    df_h4["atr"] = (df_h4["high"] - df_h4["low"]).rolling(14).mean()
    df_h4["volume_sma"] = df_h4["volume"].rolling(20).mean()

    for i in range(2, len(df_h4)):
        bar1 = df_h4.iloc[i - 2]  # Previous
        bar2 = df_h4.iloc[i - 1]  # Current (potential FVG creator)
        bar3 = df_h4.iloc[i]  # Next

        timestamp = df_h4.index[i - 1]

        # Check for bullish FVG: bar1.high < bar3.low
        if bar1["high"] < bar3["low"]:
            gap_size = bar3["low"] - bar1["high"]
            gap_pct = (gap_size / bar2["close"]) * 100

            # Quality checks
            atr_value = (
                bar2["atr"]
                if not pd.isna(bar2["atr"])
                else (bar2["high"] - bar2["low"])
            )
            vol_ratio = (
                bar2["volume"] / bar2["volume_sma"] if bar2["volume_sma"] > 0 else 1.0
            )

            atr_ok = (
                gap_size > (atr_value * min_gap_atr) if not pd.isna(atr_value) else True
            )
            pct_ok = gap_pct > min_gap_pct
            vol_ok = vol_ratio >= min_rel_vol

            fvg_quality = atr_ok and pct_ok and vol_ok

            fvgs_detected.append(
                {
                    "timestamp": timestamp,
                    "type": "bullish",
                    "top": bar3["low"],
                    "bottom": bar1["high"],
                    "gap_size": gap_size,
                    "gap_pct": gap_pct,
                    "atr_ok": atr_ok,
                    "pct_ok": pct_ok,
                    "vol_ok": vol_ok,
                    "quality_pass": fvg_quality,
                    "atr_value": atr_value,
                    "vol_ratio": vol_ratio,
                }
            )

        # Check for bearish FVG: bar1.low > bar3.high
        elif bar1["low"] > bar3["high"]:
            gap_size = bar1["low"] - bar3["high"]
            gap_pct = (gap_size / bar2["close"]) * 100

            # Quality checks
            atr_value = (
                bar2["atr"]
                if not pd.isna(bar2["atr"])
                else (bar2["high"] - bar2["low"])
            )
            vol_ratio = (
                bar2["volume"] / bar2["volume_sma"] if bar2["volume_sma"] > 0 else 1.0
            )

            atr_ok = (
                gap_size > (atr_value * min_gap_atr) if not pd.isna(atr_value) else True
            )
            pct_ok = gap_pct > min_gap_pct
            vol_ok = vol_ratio >= min_rel_vol

            fvg_quality = atr_ok and pct_ok and vol_ok

            fvgs_detected.append(
                {
                    "timestamp": timestamp,
                    "type": "bearish",
                    "top": bar1["low"],
                    "bottom": bar3["high"],
                    "gap_size": gap_size,
                    "gap_pct": gap_pct,
                    "atr_ok": atr_ok,
                    "pct_ok": pct_ok,
                    "vol_ok": vol_ok,
                    "quality_pass": fvg_quality,
                    "atr_value": atr_value,
                    "vol_ratio": vol_ratio,
                }
            )

    print(f"Total FVGs detected: {len(fvgs_detected)}")
    print(
        f"Quality FVGs (passing all filters): {sum(1 for fvg in fvgs_detected if fvg['quality_pass'])}"
    )
    print()

    if fvgs_detected:
        print("FVG Details:")
        for fvg in fvgs_detected:
            status = "✅ PASS" if fvg["quality_pass"] else "❌ FAIL"
            print(
                f"  {fvg['timestamp'].strftime('%Y-%m-%d %H:%M')} | {fvg['type'].upper():8} | {status}"
            )
            print(
                f"    Gap: ${fvg['gap_size']:.2f} ({fvg['gap_pct']:.3f}%) | ATR: {'✅' if fvg['atr_ok'] else '❌'} | PCT: {'✅' if fvg['pct_ok'] else '❌'} | VOL: {'✅' if fvg['vol_ok'] else '❌'}"
            )
            if not fvg["quality_pass"]:
                print(
                    f"    ATR check: {fvg['gap_size']:.2f} > {fvg['atr_value'] * min_gap_atr:.2f} = {fvg['atr_ok']}"
                )
                print(
                    f"    Vol check: {fvg['vol_ratio']:.2f} >= {min_rel_vol} = {fvg['vol_ok']}"
                )
    else:
        print("❌ No FVGs detected!")
        print("💡 This explains why no signals were generated")

    print()

    # Step 3: Focus on the May 20 period
    print("🎯 STEP 3: May 20 Focus Analysis")
    print("-" * 30)

    # Find FVGs around May 20
    may_20_fvgs = [
        fvg
        for fvg in fvgs_detected
        if fvg["timestamp"].date() == pd.Timestamp("2025-05-20").date()
    ]

    if may_20_fvgs:
        print("May 20 FVGs found:")
        for fvg in may_20_fvgs:
            print(
                f"  {fvg['timestamp'].strftime('%H:%M')} | {fvg['type'].upper()} | Quality: {'✅' if fvg['quality_pass'] else '❌'}"
            )
    else:
        print("❌ No FVGs detected on May 20")

        # Check what was happening around 16:00
        target_time = pd.Timestamp("2025-05-20 16:00:00+00:00")
        h4_around_16 = df_h4.loc[
            target_time - timedelta(hours=8) : target_time + timedelta(hours=4)
        ]

        print("\nH4 bars around May 20 16:00:")
        for ts, bar in h4_around_16.iterrows():
            print(
                f"  {ts.strftime('%Y-%m-%d %H:%M')} | O:{bar['open']:.2f} H:{bar['high']:.2f} L:{bar['low']:.2f} C:{bar['close']:.2f}"
            )

        # Check why no FVG was detected
        if len(h4_around_16) >= 3:
            bars = h4_around_16.iloc[-3:]
            bar1, bar2, bar3 = bars.iloc[0], bars.iloc[1], bars.iloc[2]

            print("\n3-bar pattern analysis:")
            print(f"  Bar1 (prev): H:{bar1['high']:.2f} L:{bar1['low']:.2f}")
            print(f"  Bar2 (curr): H:{bar2['high']:.2f} L:{bar2['low']:.2f}")
            print(f"  Bar3 (next): H:{bar3['high']:.2f} L:{bar3['low']:.2f}")

            # Check gaps
            bullish_gap = bar1["high"] < bar3["low"]
            bearish_gap = bar1["low"] > bar3["high"]

            print(
                f"  Bullish gap: {bullish_gap} (bar1.high {bar1['high']:.2f} < bar3.low {bar3['low']:.2f})"
            )
            print(
                f"  Bearish gap: {bearish_gap} (bar1.low {bar1['low']:.2f} > bar3.high {bar3['high']:.2f})"
            )

    print("\n" + "=" * 50)
    print("📋 PIPELINE DIAGNOSIS SUMMARY")
    print("=" * 50)

    if len(fvgs_detected) == 0:
        print("❌ ROOT CAUSE: No FVGs detected at H4 level")
        print("💡 SOLUTIONS:")
        print("  1. Check if data aggregation is working correctly")
        print("  2. Verify FVG detection thresholds are not too strict")
        print("  3. Consider using lower timeframe (H1) for more signals")
    elif sum(1 for fvg in fvgs_detected if fvg["quality_pass"]) == 0:
        print("❌ ROOT CAUSE: FVGs detected but all fail quality filters")
        print("💡 SOLUTIONS:")
        print("  1. Relax min_gap_atr threshold further")
        print("  2. Relax min_gap_pct threshold further")
        print("  3. Disable volume filter in FVG detection")
    else:
        quality_fvgs = [fvg for fvg in fvgs_detected if fvg["quality_pass"]]
        print(f"✅ {len(quality_fvgs)} quality FVGs detected")
        print("💡 Issue may be in signal candidate processing or zone touching logic")


if __name__ == "__main__":
    trace_signal_pipeline()
