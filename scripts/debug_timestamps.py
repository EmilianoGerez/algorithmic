#!/usr/bin/env python3
"""
Debug Timestamp Format Issues
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


def debug_timestamp_formats():
    """Debug timestamp format issues"""
    
    print("🔍 Debugging Timestamp Formats")
    print("=" * 50)
    
    # Initialize dependencies
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Get some FVG data
    symbol = "BTC/USD"
    htf = "4H"
    
    htf_pools = service.get_liquidity_pools(symbol, htf, "all")
    fvg_pools = htf_pools.get('fvg_pools', [])
    
    print(f"📊 Found {len(fvg_pools)} FVG pools")
    
    if fvg_pools:
        print(f"\n🔍 Sample FVG data:")
        sample_fvg = fvg_pools[0]
        
        for key, value in sample_fvg.items():
            print(f"   {key}: {value} (type: {type(value)})")
            
            if 'time' in key.lower():
                print(f"      • Raw value: {repr(value)}")
                try:
                    parsed = pd.to_datetime(value, utc=True)
                    print(f"      • Parsed: {parsed}")
                except Exception as e:
                    print(f"      • Parse error: {e}")
    
    # Get some candle data
    ltf = "15T"
    start = "2025-05-29T13:00:00Z"
    end = "2025-05-29T16:00:00Z"
    
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe=ltf,
        start=start,
        end=end
    )
    candles_ltf = ltf_result["candles"]
    
    print(f"\n📊 Found {len(candles_ltf)} candles")
    
    if candles_ltf:
        print(f"\n🔍 Sample candle data:")
        sample_candle = candles_ltf[0]
        
        for key, value in sample_candle.items():
            print(f"   {key}: {value} (type: {type(value)})")
            
            if 'time' in key.lower():
                print(f"      • Raw value: {repr(value)}")
                try:
                    parsed = pd.to_datetime(value, utc=True)
                    print(f"      • Parsed: {parsed}")
                except Exception as e:
                    print(f"      • Parse error: {e}")
    
    # Test our comparison
    print(f"\n🔍 Testing timestamp comparison:")
    
    if fvg_pools and candles_ltf:
        fvg_time = fvg_pools[0]['timestamp']
        candle_time = candles_ltf[0]['timestamp']
        
        print(f"   FVG timestamp: {fvg_time} (type: {type(fvg_time)})")
        print(f"   Candle timestamp: {candle_time} (type: {type(candle_time)})")
        
        try:
            fvg_parsed = pd.to_datetime(fvg_time, utc=True)
            candle_parsed = pd.to_datetime(candle_time, utc=True)
            
            print(f"   FVG parsed: {fvg_parsed}")
            print(f"   Candle parsed: {candle_parsed}")
            
            # Test comparison
            result = fvg_parsed <= candle_parsed
            print(f"   Comparison (FVG <= Candle): {result}")
            
        except Exception as e:
            print(f"   Comparison error: {e}")
    
    print(f"\n✅ Debug Complete!")
    db.close()


if __name__ == "__main__":
    debug_timestamp_formats()
