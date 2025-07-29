"""
Debug script using actual configuration values from base.yaml
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yaml


def debug_with_config():
    """Debug using actual configuration from base.yaml."""

    print("🐛 SIGNAL FILTERING DEBUG (Using base.yaml config)")
    print("=" * 50)

    # Load configuration
    with open("configs/base.yaml") as f:
        config = yaml.safe_load(f)

    print("📋 Current Configuration:")
    print(f"   Volume multiple: {config['candidate']['filters']['volume_multiple']}")
    print(f"   Linger minutes: {config['candidate']['filters']['linger_minutes']}")
    print(f"   Min gap ATR: {config['detectors']['fvg']['min_gap_atr']}")
    print(f"   Min gap PCT: {config['detectors']['fvg']['min_gap_pct']}")
    print(f"   Min rel vol: {config['detectors']['fvg']['min_rel_vol']}")
    print()

    # Load data
    df = pd.read_csv("data/BTC_USD_5min_20250728_021825.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    # Calculate indicators
    df["ema21"] = df["close"].ewm(span=21).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["volume_sma"] = df["volume"].rolling(20).mean()

    # Focus on May 20, 16:00 signal
    signal_time = pd.Timestamp("2025-05-20 16:00:00+00:00")
    entry_level = 105716.49

    signal_bar = df[df["timestamp"] == signal_time].iloc[0]

    print(f"🎯 Signal Time: {signal_time}")
    print(f"💰 Entry Level: ${entry_level:.2f}")
    print(
        f"📊 Signal Bar: Price=${signal_bar['close']:.2f}, Volume={signal_bar['volume']}"
    )
    print()

    # Check filters with actual config values
    print("🔍 FILTER ANALYSIS (Updated Config)")
    print("-" * 40)

    # 1. Volume Filter (updated to 1.0)
    volume_multiple = config["candidate"]["filters"]["volume_multiple"]
    volume_ok = signal_bar["volume"] >= (signal_bar["volume_sma"] * volume_multiple)
    print(f"1. Volume Filter: {'✅ PASS' if volume_ok else '❌ FAIL'}")
    print(
        f"   Volume ({signal_bar['volume']}) >= SMA*{volume_multiple} ({signal_bar['volume_sma'] * volume_multiple})"
    )

    # Handle the case where volume is 0
    if signal_bar["volume"] == 0 and signal_bar["volume_sma"] == 0:
        # If both are 0, we should disable volume filter
        volume_ok_relaxed = True
        print("   🔧 Volume data unavailable - considering PASS for this analysis")
    else:
        volume_ok_relaxed = volume_ok

    # 2. FVG Quality with updated parameters
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

    # Calculate H4 ATR properly
    df_h4["atr"] = (df_h4["high"] - df_h4["low"]).rolling(14).mean()

    h4_bar_time = signal_time.floor("4h")
    h4_bars = df_h4.loc[
        h4_bar_time - timedelta(hours=8) : h4_bar_time + timedelta(hours=4)
    ]

    if len(h4_bars) >= 3:
        bars = h4_bars.iloc[-3:]
        bar1, bar2, bar3 = bars.iloc[0], bars.iloc[1], bars.iloc[2]

        # Bullish FVG check
        gap_exists = bar1["high"] < bar3["low"]
        gap_size = bar3["low"] - bar1["high"] if gap_exists else 0
        gap_pct = (gap_size / bar2["close"]) * 100 if gap_exists else 0

        # Get ATR for quality check
        atr_value = (
            bar2["atr"] if not np.isnan(bar2["atr"]) else (bar2["high"] - bar2["low"])
        )

        # Updated thresholds
        min_gap_atr = config["detectors"]["fvg"]["min_gap_atr"]
        min_gap_pct = config["detectors"]["fvg"]["min_gap_pct"]

        atr_ok = (
            gap_size > (atr_value * min_gap_atr) if not np.isnan(atr_value) else True
        )
        pct_ok = gap_pct > min_gap_pct

        print(f"2. FVG Quality: {'✅ PASS' if (atr_ok and pct_ok) else '❌ FAIL'}")
        print(f"   Gap: ${gap_size:.2f} ({gap_pct:.3f}%)")
        print(
            f"   ATR check: {'✅' if atr_ok else '❌'} (need >{atr_value * min_gap_atr:.2f})"
        )
        print(f"   PCT check: {'✅' if pct_ok else '❌'} (need >{min_gap_pct}%)")

        fvg_quality_ok = atr_ok and pct_ok
    else:
        print("2. FVG Quality: ❌ FAIL (insufficient data)")
        fvg_quality_ok = False

    # Other filters (unchanged)
    ema_aligned = signal_bar["close"] > signal_bar["ema21"]
    in_killzone = 1 <= signal_time.hour <= 18

    print(f"3. EMA Alignment: {'✅ PASS' if ema_aligned else '❌ FAIL'}")
    print(f"4. Killzone: {'✅ PASS' if in_killzone else '❌ FAIL'}")

    print("\n" + "=" * 50)
    print("📋 UPDATED FILTER RESULTS")
    print("=" * 50)

    all_pass = volume_ok_relaxed and fvg_quality_ok and ema_aligned and in_killzone

    filters_status = [
        ("Volume (relaxed)", volume_ok_relaxed),
        ("FVG Quality", fvg_quality_ok),
        ("EMA Alignment", ema_aligned),
        ("Killzone", in_killzone),
    ]

    for name, passed in filters_status:
        print(f"{name:20} | {'✅ PASS' if passed else '❌ FAIL'}")

    if all_pass:
        print("\n🎉 ALL KEY FILTERS PASS!")
        print("💡 Signal should be generated with updated config")
    else:
        failed = [name for name, passed in filters_status if not passed]
        print(f"\n❌ Still failing: {', '.join(failed)}")

        # Provide solutions
        print("\n🔧 SOLUTIONS:")
        if not volume_ok_relaxed:
            print("• Disable volume filter entirely (set volume_multiple: 0)")
        if not fvg_quality_ok:
            print("• Further reduce min_gap_atr to 0.05")
            print("• Further reduce min_gap_pct to 0.01")


if __name__ == "__main__":
    debug_with_config()
