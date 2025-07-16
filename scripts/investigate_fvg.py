#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.db.models.fvg import FVG

def investigate_fvg_detection():
    print("🔍 Investigating H4 FVG Detection")
    print("=" * 50)
    
    # Parameters
    symbol = "BTC/USD"
    htf = "4H"
    start = "2025-07-01T00:00:00Z"
    end = "2025-07-13T00:00:00Z"
    
    try:
        # Initialize dependencies
        repo = AlpacaCryptoRepository()
        redis = get_redis_connection()
        db = SessionLocal()
        service = SignalDetectionService(repo, redis, db)
        
        print(f"📊 Time Window: {start} to {end}")
        print(f"📊 Symbol: {symbol}, Timeframe: {htf}")
        
        # Get HTF pools with detailed info
        htf_pools = service.get_liquidity_pools(symbol, htf, "all")
        
        print(f"\n📈 HTF Pools Summary:")
        print(f"  • FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
        print(f"  • Pivot Pools: {len(htf_pools.get('pivot_pools', []))}")
        
        # Show detailed FVG information
        fvg_pools = htf_pools.get('fvg_pools', [])
        if fvg_pools:
            print(f"\n📈 FVG Details:")
            for i, fvg in enumerate(fvg_pools):
                print(f"  {i+1}. Time: {fvg['timestamp']}")
                print(f"     Zone: {fvg['zone_low']:.2f} - {fvg['zone_high']:.2f}")
                print(f"     Direction: {fvg['direction']}")
                print(f"     Status: {fvg['status']}")
                print(f"     Strength: {fvg['strength']}")
                print(f"     Size: {fvg['zone_high'] - fvg['zone_low']:.2f}")
                
                # Check if this FVG is within our time window
                fvg_time_str = fvg['timestamp']
                if isinstance(fvg_time_str, str):
                    if fvg_time_str.endswith('Z'):
                        fvg_time = datetime.fromisoformat(fvg_time_str.replace('Z', '+00:00'))
                    else:
                        fvg_time = datetime.fromisoformat(fvg_time_str)
                else:
                    fvg_time = fvg_time_str
                
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end.replace('Z', '+00:00'))
                
                # Make sure all datetimes are timezone-aware
                if fvg_time.tzinfo is None:
                    fvg_time = fvg_time.replace(tzinfo=timezone.utc)
                
                in_window = start_time <= fvg_time <= end_time
                print(f"     In Time Window: {in_window}")
                print()
        else:
            print("\n❌ No FVG pools found")
        
        # Check database directly
        print(f"\n💾 Database Analysis:")
        
        # Count all FVGs for this symbol and timeframe
        total_fvgs = db.query(FVG).filter(
            FVG.symbol == symbol,
            FVG.timeframe == htf
        ).count()
        print(f"  • Total FVGs in DB: {total_fvgs}")
        
        # Count FVGs in our time window
        fvgs_in_window = db.query(FVG).filter(
            FVG.symbol == symbol,
            FVG.timeframe == htf,
            FVG.timestamp >= start,
            FVG.timestamp <= end
        ).count()
        print(f"  • FVGs in time window: {fvgs_in_window}")
        
        # Get some sample FVGs to see their timestamps
        sample_fvgs = db.query(FVG).filter(
            FVG.symbol == symbol,
            FVG.timeframe == htf
        ).order_by(FVG.timestamp.desc()).limit(10).all()
        
        if sample_fvgs:
            print(f"\n📅 Sample FVG Timestamps (last 10):")
            for fvg in sample_fvgs:
                print(f"  • {fvg.timestamp} - {fvg.status} - Zone: {fvg.zone_low:.2f}-{fvg.zone_high:.2f}")
        
        # Check if we have any active FVGs in the pool
        active_fvgs = db.query(FVG).filter(
            FVG.symbol == symbol,
            FVG.timeframe == htf,
            FVG.status == "active"
        ).count()
        print(f"\n🔥 Active FVGs in DB: {active_fvgs}")
        
        # Check the specific time window for raw candle data
        print(f"\n📊 Getting raw candle data for analysis...")
        result = service.detect_signals(
            symbol=symbol,
            signal_type="fvg",
            timeframe=htf,
            start=start,
            end=end
        )
        
        candles = result.get("candles", [])
        print(f"  • Candles in window: {len(candles)}")
        
        if candles:
            print(f"  • First candle: {candles[0]['timestamp']}")
            print(f"  • Last candle: {candles[-1]['timestamp']}")
            
            # Analyze for potential FVGs manually
            print(f"\n🔍 Manual FVG Analysis:")
            potential_fvgs = 0
            for i in range(2, len(candles)):
                prev_candle = candles[i-2]
                curr_candle = candles[i-1]
                next_candle = candles[i]
                
                # Check for bullish FVG
                if (prev_candle['low'] > next_candle['high'] and 
                    curr_candle['close'] > curr_candle['open']):  # Bullish candle
                    potential_fvgs += 1
                
                # Check for bearish FVG
                if (prev_candle['high'] < next_candle['low'] and 
                    curr_candle['close'] < curr_candle['open']):  # Bearish candle
                    potential_fvgs += 1
            
            print(f"  • Potential FVGs found: {potential_fvgs}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    investigate_fvg_detection()
