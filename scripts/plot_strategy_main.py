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
from plot_strategy import plot_candles_with_signals_and_4h_fvg

# Initialize dependencies
repo = AlpacaCryptoRepository()
redis = get_redis_connection()
db = SessionLocal()
service = SignalDetectionService(repo, redis, db)

# Parameters - Multi-Timeframe Analysis
symbol = "BTC/USD"
ltf = "15T"  # Low timeframe for entries (15-minute candles)
htf = "4H"   # High timeframe for context (Daily)
start = "2025-07-01T00:00:00Z"
end = "2025-07-13T00:00:00Z"

print("🚀 Multi-Timeframe Signal Detection")
print("=" * 50)

# Method 1: Use new multi-timeframe engine
print("\n1. Using New Multi-Timeframe Engine:")
signals = service.detect_multi_timeframe_signals(
    symbol=symbol,
    strategy_type="intraday",  # Uses 15T LTF + 4H HTF
    start=start,
    end=end,
    update_pools=True
)

print(f"📊 Detected {len(signals)} high-quality signals")
for i, signal in enumerate(signals[:5]):  # Show top 5
    print(f"  {i+1}. {signal.signal_type.value} - {signal.direction} - "
          f"Price: ${signal.price:.2f} - Strength: {signal.strength.name} - "
          f"Confidence: {signal.confidence:.2f}")

# Method 2: Get liquidity pools for plotting
print("\n2. Getting Liquidity Pools for Plotting:")
htf_pools = service.get_liquidity_pools(symbol, htf, "all")

# Get LTF candles using the legacy method for compatibility with plotting
ltf_result = service.detect_signals(
    symbol=symbol,
    signal_type="fvg_and_pivot",
    timeframe=ltf,
    start=start,
    end=end
)
candles_ltf = ltf_result["candles"]

print(f"📈 HTF Pools - FVG: {len(htf_pools.get('fvg_pools', []))}, Pivots: {len(htf_pools.get('pivot_pools', []))}")
print(f"📊 LTF Candles: {len(candles_ltf)}")

# Format data for plotting (maintain compatibility with existing plot function)
# Format pivots
pivot_data = [
    {
        "timestamp": pool["timestamp"],
        "price": pool["price_level"],
        "type": pool["pivot_type"]
    } for pool in htf_pools.get("pivot_pools", [])
]

# Format FVGs
fvg_data = [
    {
        "timestamp": pool["timestamp"],
        "zone": [pool["zone_low"], pool["zone_high"]],
        "direction": pool["direction"],
        "iFVG": pool["is_inverse"]
    } for pool in htf_pools.get("fvg_pools", [])
]

print(f"\n📊 Data for plotting:")
print(f"  Pivot data points: {len(pivot_data)}")
print(f"  FVG data points: {len(fvg_data)}")
print(f"  Signals: {len(signals)}")

# Plot with the FVG and pivot data and signals
plot_candles_with_signals_and_4h_fvg(
    candles_ltf,
    pivots=pivot_data,
    tracked_fvgs_4h=fvg_data,
    signals=signals,
    save_path="plot.png"
)

print("\n✅ Plot saved to plot.png")
print("\n📊 Summary:")
print(f"  • LTF Candles ({ltf}): {len(candles_ltf)}")
print(f"  • HTF Pivot Points ({htf}): {len(pivot_data)}")
print(f"  • HTF FVG Zones ({htf}): {len(fvg_data)}")

# Show cache statistics
cache_stats = service.get_cache_stats()
print(f"\n💾 Cache Performance:")
print(f"  • Memory cache entries: {cache_stats['memory_cache_size']}")
print(f"  • Redis connected: {cache_stats['redis_connected']}")

print(f"\n🎯 Strategy Summary:")
print(f"  • Using {ltf} for entries and {htf} for context")
print(f"  • New MTF engine provides higher quality signals")
print(f"  • Enhanced caching improves performance")
print(f"  • Real-time ready architecture")
