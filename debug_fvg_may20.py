#!/usr/bin/env python3
"""
Manual FVG Analysis for May 20, 2025 around 14:00 (16:00 UTC)

This script manually analyzes the BTCUSDT data to identify FVGs and potential entry points
around the time period you mentioned for the trading scenario.
"""

from datetime import datetime, timezone

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def detect_fvg_simple(df, i):
    """Simple FVG detection: gap between candle i-1 and i+1 not filled by candle i"""
    if i < 1 or i >= len(df) - 1:
        return None

    prev_candle = df.iloc[i - 1]
    curr_candle = df.iloc[i]
    next_candle = df.iloc[i + 1]

    # Bullish FVG: previous low > next high (gap up)
    if prev_candle["low"] > next_candle["high"]:
        gap_size = prev_candle["low"] - next_candle["high"]
        gap_pct = (gap_size / curr_candle["close"]) * 100
        return {
            "type": "bullish",
            "time": curr_candle["timestamp"],
            "upper": prev_candle["low"],
            "lower": next_candle["high"],
            "gap_size": gap_size,
            "gap_pct": gap_pct,
        }

    # Bearish FVG: previous high < next low (gap down)
    elif prev_candle["high"] < next_candle["low"]:
        gap_size = next_candle["low"] - prev_candle["high"]
        gap_pct = (gap_size / curr_candle["close"]) * 100
        return {
            "type": "bearish",
            "time": curr_candle["timestamp"],
            "upper": next_candle["low"],
            "lower": prev_candle["high"],
            "gap_size": gap_size,
            "gap_pct": gap_pct,
        }

    return None


def analyze_may_20_fvgs():
    """Analyze FVGs around May 20, 14:00"""

    # Load the data
    df = pd.read_csv("data/BTCUSDT_5m_may19-20_fvg_analysis.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print("🔍 FVG Analysis for May 19-20, 2025")
    print("=" * 50)

    # Focus on May 20 around 14:00-18:00 (your target time window)
    focus_start = pd.to_datetime("2025-05-20 14:00:00+00:00")
    focus_end = pd.to_datetime("2025-05-20 18:00:00+00:00")

    print(f"📅 Data range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"🎯 Focus window: {focus_start} to {focus_end}")
    print(f"📊 Total bars: {len(df)}")

    # Detect all FVGs
    fvgs = []
    for i in range(1, len(df) - 1):
        fvg = detect_fvg_simple(df, i)
        if fvg:
            fvgs.append(fvg)

    print(f"\n💎 Total FVGs detected: {len(fvgs)}")

    # Filter FVGs for the focus period
    focus_fvgs = [fvg for fvg in fvgs if focus_start <= fvg["time"] <= focus_end]
    print(f"🎯 FVGs in focus window: {len(focus_fvgs)}")

    # Show all FVGs in focus period
    print("\n📋 FVGs around May 20, 14:00-18:00:")
    for fvg in focus_fvgs:
        print(
            f"  {fvg['time'].strftime('%H:%M')} | {fvg['type']:<8} | Gap: {fvg['gap_size']:.1f} ({fvg['gap_pct']:.3f}%) | Range: {fvg['lower']:.1f} - {fvg['upper']:.1f}"
        )

    # Show broader context - FVGs from entire period
    print("\n📋 All FVGs on May 19-20 (showing largest gaps):")
    sorted_fvgs = sorted(fvgs, key=lambda x: x["gap_pct"], reverse=True)[:15]
    for fvg in sorted_fvgs:
        time_str = fvg["time"].strftime("%Y-%m-%d %H:%M")
        print(
            f"  {time_str} | {fvg['type']:<8} | Gap: {fvg['gap_size']:.1f} ({fvg['gap_pct']:.3f}%) | Range: {fvg['lower']:.1f} - {fvg['upper']:.1f}"
        )

    # Analyze price movement around May 20, 14:00
    focus_df = df[
        (df["timestamp"] >= focus_start) & (df["timestamp"] <= focus_end)
    ].copy()
    print("\n📈 Price action during focus window:")
    print(
        f"  Start: {focus_df.iloc[0]['close']:.1f} at {focus_df.iloc[0]['timestamp'].strftime('%H:%M')}"
    )
    print(
        f"  End: {focus_df.iloc[-1]['close']:.1f} at {focus_df.iloc[-1]['timestamp'].strftime('%H:%M')}"
    )
    print(f"  High: {focus_df['high'].max():.1f}")
    print(f"  Low: {focus_df['low'].min():.1f}")
    print(f"  Range: {focus_df['high'].max() - focus_df['low'].min():.1f} points")

    # Look for price touching existing FVGs during focus period
    print("\n🎯 Checking if price touched any existing FVGs during focus window...")
    focus_low = focus_df["low"].min()
    focus_high = focus_df["high"].max()

    # FVGs created before the focus period that could be touched
    pre_fvgs = [fvg for fvg in fvgs if fvg["time"] < focus_start]
    touched_fvgs = []

    for fvg in pre_fvgs:
        # Check if price entered the FVG range during focus period
        if (
            fvg["type"] == "bullish"
            and focus_low <= fvg["upper"]
            and focus_high >= fvg["lower"]
        ) or (
            fvg["type"] == "bearish"
            and focus_low <= fvg["upper"]
            and focus_high >= fvg["lower"]
        ):
            touched_fvgs.append(fvg)

    print(
        f"  Found {len(touched_fvgs)} pre-existing FVGs that were touched during focus window:"
    )
    for fvg in touched_fvgs:
        created_time = fvg["time"].strftime("%Y-%m-%d %H:%M")
        print(
            f"    {created_time} | {fvg['type']:<8} | Range: {fvg['lower']:.1f} - {fvg['upper']:.1f} | Gap: {fvg['gap_pct']:.3f}%"
        )

    return fvgs, focus_fvgs, touched_fvgs, df, focus_df


def create_chart(df, fvgs, focus_start, focus_end):
    """Create a chart showing price action and FVGs"""

    # Filter for extended view around focus period
    chart_start = pd.to_datetime("2025-05-20 10:00:00+00:00")
    chart_end = pd.to_datetime("2025-05-20 20:00:00+00:00")
    chart_df = df[
        (df["timestamp"] >= chart_start) & (df["timestamp"] <= chart_end)
    ].copy()

    plt.figure(figsize=(15, 8))

    # Plot candlesticks (simplified)
    plt.plot(
        chart_df["timestamp"], chart_df["close"], "b-", linewidth=1, label="Close Price"
    )
    plt.fill_between(
        chart_df["timestamp"],
        chart_df["low"],
        chart_df["high"],
        alpha=0.3,
        color="lightblue",
    )

    # Plot FVGs in the chart window
    chart_fvgs = [fvg for fvg in fvgs if chart_start <= fvg["time"] <= chart_end]

    for fvg in chart_fvgs:
        color = "green" if fvg["type"] == "bullish" else "red"
        alpha = 0.3
        plt.fill_between(
            [
                fvg["time"] - pd.Timedelta(minutes=15),
                fvg["time"] + pd.Timedelta(minutes=15),
            ],
            fvg["lower"],
            fvg["upper"],
            color=color,
            alpha=alpha,
            label=f"{fvg['type']} FVG" if fvg == chart_fvgs[0] else "",
        )

    # Highlight focus window
    plt.axvspan(
        focus_start,
        focus_end,
        color="yellow",
        alpha=0.2,
        label="Focus Window (14:00-18:00)",
    )

    plt.title("BTCUSDT 5min - May 20, 2025 - FVG Analysis")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Format x-axis
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=2))
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig("may_20_fvg_analysis.png", dpi=150, bbox_inches="tight")
    print("\n📊 Chart saved as 'may_20_fvg_analysis.png'")
    plt.show()


if __name__ == "__main__":
    try:
        fvgs, focus_fvgs, touched_fvgs, df, focus_df = analyze_may_20_fvgs()

        # Create visualization
        focus_start = pd.to_datetime("2025-05-20 14:00:00+00:00")
        focus_end = pd.to_datetime("2025-05-20 18:00:00+00:00")
        create_chart(df, fvgs, focus_start, focus_end)

        print("\n✅ Analysis complete! Found potential FVG entry opportunities.")
        if touched_fvgs:
            print(
                f"🎯 Key finding: {len(touched_fvgs)} pre-existing FVGs were touched during your target time window"
            )
            print(
                "    This suggests potential entry opportunities around May 20, 14:00-18:00"
            )
        else:
            print("⚠️  No pre-existing FVGs were touched during the focus window")
            print(
                "    Consider expanding the time window or looking at different timeframes"
            )

    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback

        traceback.print_exc()
