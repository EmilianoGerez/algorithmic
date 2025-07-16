#!/usr/bin/env python3
"""
Debug Time Window Strategy
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
import pandas as pd
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.core.strategy.detectors.liquidity_pool_detectors import FVGPoolDetector, PivotPoolDetector


def debug_time_window_strategy():
    """Debug the time window strategy step by step"""
    
    print("🔍 Debug Time Window Strategy")
    print("=" * 50)
    
    # Initialize dependencies
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Parameters
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    start = "2025-05-15T00:00:00Z"
    end = "2025-06-15T00:00:00Z"
    
    # Get data
    print(f"📥 Loading Data...")
    htf_pools = service.get_liquidity_pools(symbol, htf, "all")
    
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe=ltf,
        start=start,
        end=end
    )
    candles_ltf = ltf_result["candles"]
    
    print(f"   • LTF Candles: {len(candles_ltf)}")
    print(f"   • HTF FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
    print(f"   • HTF Pivot Pools: {len(htf_pools.get('pivot_pools', []))}")
    
    # Get first few pool events
    fvg_pools = htf_pools.get('fvg_pools', [])[:3]
    pivot_pools = htf_pools.get('pivot_pools', [])[:3]
    
    fvg_detector = FVGPoolDetector()
    pivot_detector = PivotPoolDetector()
    
    fvg_events = fvg_detector.detect_events(candles_ltf, fvg_pools)
    pivot_events = pivot_detector.detect_events(candles_ltf, pivot_pools)
    
    all_pool_events = fvg_events + pivot_events
    print(f"   • Pool Events: {len(all_pool_events)}")
    
    # Test first pool event
    if all_pool_events:
        pool_event = all_pool_events[0]
        print(f"\n🎯 Testing Pool Event:")
        print(f"   • Timestamp: {pool_event.timestamp}")
        print(f"   • Type: {pool_event.pool_type.value}")
        print(f"   • Status: {pool_event.status}")
        print(f"   • Price: ${pool_event.price:.2f}")
        print(f"   • Direction: {pool_event.direction.value}")
        
        # Convert to DataFrame
        df = pd.DataFrame(candles_ltf)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp')
        
        # Get time window - make it larger to ensure enough data
        pool_time = pd.to_datetime(pool_event.timestamp, utc=True)
        window_start = pool_time - pd.Timedelta(hours=6)  # 6 hours before
        window_end = pool_time + pd.Timedelta(hours=6)    # 6 hours after
        
        print(f"\n⏰ Time Window:")
        print(f"   • Pool Time: {pool_time}")
        print(f"   • Window Start: {window_start}")
        print(f"   • Window End: {window_end}")
        
        # Get window candles
        window_mask = (df['timestamp'] >= window_start) & (df['timestamp'] <= window_end)
        window_candles = df[window_mask].copy()
        
        print(f"   • Window Candles: {len(window_candles)}")
        
        if len(window_candles) >= 30:
            # Calculate EMAs
            window_candles['ema_fast'] = window_candles['close'].ewm(span=9).mean()
            window_candles['ema_slow'] = window_candles['close'].ewm(span=20).mean()
            
            # Detect crossovers
            window_candles['ema_fast_above'] = window_candles['ema_fast'] > window_candles['ema_slow']
            window_candles['ema_cross'] = window_candles['ema_fast_above'] != window_candles['ema_fast_above'].shift(1)
            
            crossovers = window_candles[window_candles['ema_cross'] & window_candles['ema_cross'].notna()]
            
            print(f"\n📊 EMA Analysis:")
            print(f"   • EMA Crossovers in Window: {len(crossovers)}")
            
            if len(crossovers) > 0:
                print(f"   • Crossover Details:")
                for idx, row in crossovers.iterrows():
                    direction = 'Bullish' if row['ema_fast_above'] else 'Bearish'
                    print(f"     - {row['timestamp']}: {direction} at ${row['close']:.2f}")
                    print(f"       EMA Fast: {row['ema_fast']:.2f}, EMA Slow: {row['ema_slow']:.2f}")
                
                # Check directional alignment
                print(f"\n🔄 Directional Alignment Check:")
                for idx, row in crossovers.iterrows():
                    ema_direction = 'bullish' if row['ema_fast_above'] else 'bearish'
                    pool_direction = pool_event.direction.value
                    
                    print(f"   • EMA Direction: {ema_direction}")
                    print(f"   • Pool Direction: {pool_direction}")
                    
                    # Check alignment based on pool type
                    if pool_event.pool_type.value == "fvg":
                        aligned = (ema_direction == pool_direction)
                        print(f"   • FVG Same Direction Required: {aligned}")
                    elif pool_event.pool_type.value == "pivot":
                        aligned = (ema_direction != pool_direction)
                        print(f"   • Pivot Opposite Direction Required: {aligned}")
                    
                    if aligned:
                        print(f"   ✅ SIGNAL WOULD BE GENERATED!")
                    else:
                        print(f"   ❌ No signal - direction mismatch")
            else:
                print(f"   ❌ No EMA crossovers found in time window")
        else:
            print(f"   ❌ Not enough candles in window for EMA calculation")
    
    print(f"\n✅ Debug Complete!")
    db.close()


if __name__ == "__main__":
    debug_time_window_strategy()
