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
from src.db.models.pivot import Pivot

def flush_and_test_detection():
    print("🧹 Flushing Database and Testing Fresh Detection")
    print("=" * 60)
    
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
        
        # Step 1: Check current database state
        print(f"\n1️⃣ Current Database State:")
        fvg_count_before = db.query(FVG).count()
        pivot_count_before = db.query(Pivot).count()
        print(f"   • FVGs: {fvg_count_before}")
        print(f"   • Pivots: {pivot_count_before}")
        
        # Step 2: Flush database
        print(f"\n2️⃣ Flushing Database...")
        db.query(FVG).delete()
        db.query(Pivot).delete()
        db.commit()
        
        # Verify flush
        fvg_count_after = db.query(FVG).count()
        pivot_count_after = db.query(Pivot).count()
        print(f"   • FVGs after flush: {fvg_count_after}")
        print(f"   • Pivots after flush: {pivot_count_after}")
        
        # Step 3: Clear Redis cache
        print(f"\n3️⃣ Clearing Redis Cache...")
        try:
            redis.flushdb()
            print("   ✅ Redis cache cleared")
        except Exception as e:
            print(f"   ⚠️ Redis cache clear failed: {e}")
        
        # Step 4: Run fresh detection
        print(f"\n4️⃣ Running Fresh FVG Detection...")
        
        # Force fresh detection by running the signal detection service
        result = service.detect_signals(
            symbol=symbol,
            signal_type="fvg",
            timeframe=htf,
            start=start,
            end=end
        )
        
        print(f"   ✅ Detection completed")
        print(f"   • Candles processed: {len(result.get('candles', []))}")
        print(f"   • Signals detected: {len(result.get('signals', []))}")
        
        # Step 5: Check database after detection
        print(f"\n5️⃣ Database State After Detection:")
        fvg_count_new = db.query(FVG).count()
        pivot_count_new = db.query(Pivot).count()
        print(f"   • FVGs: {fvg_count_new}")
        print(f"   • Pivots: {pivot_count_new}")
        
        # Step 6: Show detected FVGs
        if fvg_count_new > 0:
            print(f"\n6️⃣ Detected FVGs:")
            new_fvgs = db.query(FVG).filter(
                FVG.symbol == symbol,
                FVG.timeframe == htf
            ).all()
            
            for i, fvg in enumerate(new_fvgs):
                print(f"   {i+1}. Time: {fvg.timestamp}")
                print(f"      Zone: {fvg.zone_low:.2f} - {fvg.zone_high:.2f}")
                print(f"      Direction: {fvg.direction}")
                print(f"      Status: {fvg.status}")
                print(f"      Size: {fvg.zone_high - fvg.zone_low:.2f}")
                print()
        else:
            print(f"\n6️⃣ No FVGs detected in the July time window")
        
        # Step 7: Run the pools detection to see if it finds anything
        print(f"\n7️⃣ Testing Liquidity Pools Detection...")
        htf_pools = service.get_liquidity_pools(symbol, htf, "all")
        
        fvg_pools = htf_pools.get('fvg_pools', [])
        print(f"   • FVG pools found: {len(fvg_pools)}")
        
        if fvg_pools:
            print(f"   📈 Pool Details:")
            for i, pool in enumerate(fvg_pools):
                print(f"     {i+1}. {pool['timestamp']} - {pool['direction']} - {pool['status']}")
                print(f"        Zone: {pool['zone_low']:.2f} - {pool['zone_high']:.2f}")
        
        # Step 8: Test with different detection settings
        print(f"\n8️⃣ Testing Raw FVG Detection (No Filters)...")
        
        # Let's manually check the candle data for potential FVGs
        candles = result.get('candles', [])
        if len(candles) >= 3:
            print(f"   • Analyzing {len(candles)} candles...")
            
            raw_fvgs = []
            for i in range(2, len(candles)):
                candle1 = candles[i-2]  # First candle
                candle2 = candles[i-1]  # Gap candle
                candle3 = candles[i]    # Third candle
                
                # Check for bullish FVG: candle1.low > candle3.high
                if candle1['low'] > candle3['high']:
                    gap_size = candle1['low'] - candle3['high']
                    raw_fvgs.append({
                        'timestamp': candle2['timestamp'],
                        'type': 'bullish',
                        'zone_low': candle3['high'],
                        'zone_high': candle1['low'],
                        'size': gap_size
                    })
                
                # Check for bearish FVG: candle1.high < candle3.low
                if candle1['high'] < candle3['low']:
                    gap_size = candle3['low'] - candle1['high']
                    raw_fvgs.append({
                        'timestamp': candle2['timestamp'],
                        'type': 'bearish',
                        'zone_low': candle1['high'],
                        'zone_high': candle3['low'],
                        'size': gap_size
                    })
            
            print(f"   • Raw FVGs found: {len(raw_fvgs)}")
            
            if raw_fvgs:
                print(f"   📊 Raw FVG Details:")
                for i, fvg in enumerate(raw_fvgs[:10]):  # Show first 10
                    print(f"     {i+1}. {fvg['timestamp']} - {fvg['type']}")
                    print(f"        Zone: {fvg['zone_low']:.2f} - {fvg['zone_high']:.2f}")
                    print(f"        Size: {fvg['size']:.2f}")
            else:
                print(f"   ❌ No raw FVGs found - market was likely consolidating")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    flush_and_test_detection()
