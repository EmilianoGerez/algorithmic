import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.lib.plot_signals import plot_candles_with_signals
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from typing import List, Dict
from datetime import datetime
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from src.db.session import SessionLocal
db = SessionLocal()



def plot_candles_with_signals(
    candles: List[Dict],
    signal_type: str = "fvg",
    save_path: str = "signal_plot.png",
    title: str = "Market Structure Signals",
    tracked_fvgs: List[Dict] = None
):
    timestamps = [datetime.fromisoformat(c["timestamp"].replace("Z", "")) for c in candles]
    opens = [c["open"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_title(title)

    # Plot OHLC candles
    for i in range(len(candles)):
        color = "green" if closes[i] >= opens[i] else "red"
        ax.plot([timestamps[i], timestamps[i]], [lows[i], highs[i]], color="black", linewidth=0.5)
        ax.plot([timestamps[i], timestamps[i]], [opens[i], closes[i]], color=color, linewidth=2)

    # 🔵🔴 Pivot/swing markers
    if signal_type in ["swing", "pivot"]:
        high_shown = low_shown = False
        for i, c in enumerate(candles):
            if c.get("potential_swing_high"):
                ax.scatter(timestamps[i], highs[i], color="blue", marker="^", label="Swing High" if not high_shown else "")
                high_shown = True
            if c.get("potential_swing_low"):
                ax.scatter(timestamps[i], lows[i], color="red", marker="v", label="Swing Low" if not low_shown else "")
                low_shown = True

    # 📦 FVG zones
    # Add tracked FVG zones
    if signal_type == "fvg" and tracked_fvgs:
        for fvg in tracked_fvgs:
            i = fvg["index"]
            if i >= len(timestamps): continue
            ts = timestamps[i]
            low, high = fvg["zone"]
            color = "red" if fvg["iFVG"] else ("green" if fvg["direction"] == "bullish" else "purple")
            alpha = 0.3 if fvg["iFVG"] else 0.15
            label = "iFVG" if fvg["iFVG"] else "FVG"
            ax.axhspan(low, high, facecolor=color, alpha=alpha, label=label if i == 0 else "")
            ax.scatter(ts, high if fvg["direction"] == "bullish" else low, color=color, marker="x")

    # Format X-axis
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend()
    fig.autofmt_xdate()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()


if __name__ == "__main__":
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    service = SignalDetectionService(repo, redis, db)

    symbol = "BTC/USD"
    timeframe = "4H"
    start = "2025-05-15T00:00:00Z"
    end = "2025-07-22T00:00:00Z"

    result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe=timeframe,
        start=start,
        end=end
    )

    candles = result["candles"]
    tracked_fvgs = result["tracked_fvgs"]

    print(f"✅ Detected {sum(1 for c in candles if c.get('fvg_zone'))} FVG zones")
    print(f"✅ Tracked {len(tracked_fvgs)} FVGs")
    print(f"✅ Detected {len(result['signals'])} FVG Sweep CISD signals")

    plot_candles_with_signals(
        candles,
        signal_type="fvg_and_pivot",
        save_path="plot.png",
        tracked_fvgs=tracked_fvgs
    )

    print("✅ Saved plot to plot.png")

