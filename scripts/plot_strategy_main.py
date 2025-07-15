import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot
from src.services.cisd_into_4H_fvg import detect_fvg_sweep_cisd
from plot_strategy import plot_candles_with_signals_and_4h_fvg

# Initialize dependencies
repo = AlpacaCryptoRepository()
redis = get_redis_connection()
db = SessionLocal()
service = SignalDetectionService(repo, redis, db)

# Parameters
symbol = "BTC/USD"
timeframe = "15T"  # 15-minute candles
timeframe_4h = "4H"
start = "2025-05-18T00:00:00Z"
end = "2025-05-23T00:00:00Z"

# Step 1: Detect 15m candles (FVG + Pivot)
result = service.detect_signals(
    symbol=symbol,
    signal_type="fvg_and_pivot",
    timeframe=timeframe,
    start=start,
    end=end
)
candles_15m = result["candles"]

# Step 2: Load tracked 4H FVGs from DB
tracked_fvgs_4h = db.query(FVG).filter(
    FVG.symbol == symbol,
    FVG.timeframe == timeframe_4h,
    FVG.status == "open"
).all()

# Step 3: Load tracked 15m pivots
pivots = db.query(Pivot).filter(
    Pivot.symbol == symbol,
    Pivot.timeframe == "4H",
    Pivot.timestamp >= datetime.fromisoformat(start.replace("Z", ""))
).all()

# Step 4: Detect CISD entries into 4H FVGs
cisd_signals = detect_fvg_sweep_cisd(
    symbol=symbol,
    candles_15m=candles_15m,
    db=db,
    timeframe_4h=timeframe_4h,
    start=start,
    end=end
)

print(f"Detected {len(cisd_signals)} CISD signals:")
for i, signal in enumerate(cisd_signals):
    print(f"  {i+1}. {signal['timestamp']} - {signal['direction']} - Price: {signal['cisd_price']} - Type: {signal['type']}")


# Format pivots
pivot_data = [
    {
        "timestamp": p.timestamp.isoformat(),
        "price": p.price,
        "type": p.type
    } for p in pivots
]

# Format FVGs
fvg_data = [
    {
        "timestamp": f.timestamp.isoformat(),
        "zone": [f.zone_low, f.zone_high],
        "direction": f.direction,
        "iFVG": f.iFVG
    } for f in tracked_fvgs_4h
]

# Format CISDs
cisd_lines = []
for s in cisd_signals:
    direction = s["direction"]
    
    # Use the actual CISD price from the signal instead of trying to match pivots
    cisd_lines.append({
        "timestamp": s["timestamp"],
        "direction": direction,
        "price": s["cisd_price"]  # Use the actual CISD price
    })
    
    print(f"Added CISD line: {s['timestamp']} - {direction} - Price: {s['cisd_price']} - Type: {s.get('type', 'unknown')}")

print(f"Total CISD lines to plot: {len(cisd_lines)}")

# Debug: Show what we're passing to the plot function
if cisd_lines:
    print("CISD lines format:")
    for i, line in enumerate(cisd_lines[:3]):  # Show first 3
        print(f"  {i+1}. {line}")
else:
    print("WARNING: No CISD lines to plot!")

# Plot
plot_candles_with_signals_and_4h_fvg(
    candles_15m,
    pivots=pivot_data,
    tracked_fvgs_4h=fvg_data,
    cisd_signals=cisd_lines,
    save_path="plot.png"
)

print("✅ Saved plot to plot.png")
