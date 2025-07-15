import matplotlib.pyplot as plt
from typing import List, Dict
import matplotlib.dates as mdates
from datetime import datetime


def plot_candles_with_signals(
    candles: List[Dict],
    signal_type: str = "swing",
    save_path: str = "signal_plot.png",
    title: str = "Market Structure Signals"
):
    timestamps = [datetime.fromisoformat(c["timestamp"].replace("Z", "")) for c in candles]
    opens = [c["open"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_title(title)

    # Plot candles
    for i in range(len(candles)):
        color = "green" if closes[i] >= opens[i] else "red"
        ax.plot([timestamps[i], timestamps[i]], [lows[i], highs[i]], color="black")
        ax.plot([timestamps[i], timestamps[i]], [opens[i], closes[i]], color=color, linewidth=4)

    # Overlay swing points
    if signal_type == "swing":
        for i, c in enumerate(candles):
            if c.get("swing_high"):
                ax.scatter(timestamps[i], highs[i], color="blue", marker="^", label="swing_high" if i == 0 else "")
            if c.get("swing_low"):
                ax.scatter(timestamps[i], lows[i], color="red", marker="v", label="swing_low" if i == 0 else "")

    # Overlay FVG (basic marker only for now)
    if signal_type == "fvg":
        for i, c in enumerate(candles):
            if c.get("fvg_bullish"):
                ax.scatter(timestamps[i], lows[i], color="green", marker="o", label="fvg_bullish" if i == 0 else "")
            if c.get("fvg_bearish"):
                ax.scatter(timestamps[i], highs[i], color="purple", marker="x", label="fvg_bearish" if i == 0 else "")

    # Format X-axis
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend()
    fig.autofmt_xdate()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()
