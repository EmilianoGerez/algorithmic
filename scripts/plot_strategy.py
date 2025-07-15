import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from typing import List, Dict

def plot_candles_with_signals_and_4h_fvg(
    candles_15m: List[Dict],
    pivots: List[Dict],
    tracked_fvgs_4h: List[Dict],
    cisd_signals: List[Dict],
    save_path: str = "plot.png",
    title: str = "15m Chart with 4H FVG, Pivots, and CISD"
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

    # 4H FVG zones
    fvg_shown = ifvg_shown = False
    for fvg in tracked_fvgs_4h:
        ts_start = datetime.fromisoformat(fvg["timestamp"].replace("Z", ""))
        ts_end = timestamps[-1]
        low, high = fvg["zone"]
        color = "red" if fvg.get("iFVG") else ("green" if fvg["direction"] == "bullish" else "purple")
        alpha = 0.35 if fvg.get("iFVG") else 0.15
        label = "iFVG 4H" if fvg.get("iFVG") and not ifvg_shown else "FVG 4H" if not fvg.get("iFVG") and not fvg_shown else ""

        ax.fill_betweenx([low, high], ts_start, ts_end, facecolor=color, alpha=alpha, label=label)
        ax.scatter(ts_start, high if fvg["direction"] == "bullish" else low, color=color, marker="x")

        if fvg.get("iFVG"):
            ifvg_shown = True
        else:
            fvg_shown = True

    # CISD signals → 4 candle length, color-coded
    cisd_shown_bull = cisd_shown_bear = False
    candle_duration = timedelta(minutes=15)
    for signal in cisd_signals:
        ts = datetime.fromisoformat(signal["timestamp"].replace("Z", ""))
        end_ts = ts + candle_duration * 4
        level = signal["price"]
        direction = signal["direction"]

        color = "green" if direction == "bullish" else "red"
        label = "CISD Bullish" if direction == "bullish" and not cisd_shown_bull else \
                "CISD Bearish" if direction == "bearish" and not cisd_shown_bear else ""

        ax.hlines(y=level, xmin=ts, xmax=end_ts, colors=color, linestyle="--", linewidth=1.4, label=label)
        ax.scatter(ts, level, color=color, marker="D", s=60)

        if direction == "bullish":
            cisd_shown_bull = True
        else:
            cisd_shown_bear = True

    # Format X-axis
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend()
    fig.autofmt_xdate()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()
