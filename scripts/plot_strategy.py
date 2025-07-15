import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import List, Dict

def plot_candles_with_signals_and_4h_fvg(
    candles_15m: List[Dict],
    pivots: List[Dict],
    tracked_fvgs_4h: List[Dict],
    save_path: str = "plot.png",
    title: str = "15m Chart with 4H FVG and Pivots"
):
    timestamps = [datetime.fromisoformat(c["timestamp"].replace("Z", "")) for c in candles_15m]
    opens = [c["open"] for c in candles_15m]
    highs = [c["high"] for c in candles_15m]
    lows = [c["low"] for c in candles_15m]
    closes = [c["close"] for c in candles_15m]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_title(title)

    # Plot OHLC candles
    for i in range(len(candles_15m)):
        color = "green" if closes[i] >= opens[i] else "red"
        ax.plot([timestamps[i], timestamps[i]], [lows[i], highs[i]], color="black", linewidth=0.5)
        ax.plot([timestamps[i], timestamps[i]], [opens[i], closes[i]], color=color, linewidth=2)

    # Pivot highs/lows
    high_shown = low_shown = False
    for pivot in pivots:
        ts = datetime.fromisoformat(pivot["timestamp"].replace("Z", ""))
        price = pivot["price"]
        if pivot["type"] == "high":
            ax.scatter(ts, price, color="blue", marker="^", label="Swing High" if not high_shown else "")
            high_shown = True
        elif pivot["type"] == "low":
            ax.scatter(ts, price, color="red", marker="v", label="Swing Low" if not low_shown else "")
            low_shown = True

    # 4H FVG zones on 15m chart
    fvg_shown = ifvg_shown = False
    for fvg in tracked_fvgs_4h:
        ts = datetime.fromisoformat(fvg["timestamp"].replace("Z", ""))
        low, high = fvg["zone"]
        color = "red" if fvg.get("iFVG") else ("green" if fvg["direction"] == "bullish" else "purple")
        alpha = 0.35 if fvg.get("iFVG") else 0.15
        label = "iFVG 4H" if fvg.get("iFVG") and not ifvg_shown else "FVG 4H" if not fvg.get("iFVG") and not fvg_shown else ""

        ax.axhspan(low, high, facecolor=color, alpha=alpha, label=label)
        ax.scatter(ts, high if fvg["direction"] == "bullish" else low, color=color, marker="x")

        if fvg.get("iFVG"):
            ifvg_shown = True
        else:
            fvg_shown = True

    # Format X-axis
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend()
    fig.autofmt_xdate()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()
