#!/usr/bin/env python3
"""
Debug FVG Event Detection
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
import pandas as pd
from src.core.strategy.detectors.liquidity_pool_detectors import FVGPoolDetector
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


def debug_fvg_detection():
    """Debug why FVG events are not being detected"""
    
    print("🔍 Debugging FVG Event Detection")
    print("=" * 50)
    
    # Initialize 
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    fvg_detector = FVGPoolDetector()
    
    # Focus on May 29 13:30 when we know FVG touch occurred
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    start = "2025-05-29T13:00:00Z"
    end = "2025-05-29T16:00:00Z"
    
    print(f"📥 Getting data for {start} to {end}")
    
    # Get data
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe=ltf,
        start=start,
        end=end
    )
    candles_ltf = ltf_result["candles"]
    
    htf_pools = service.get_liquidity_pools(symbol, htf, "all")
    fvg_pools = htf_pools.get('fvg_pools', [])
    
    print(f"   • LTF Candles: {len(candles_ltf)}")
    print(f"   • HTF FVG Pools: {len(fvg_pools)}")
    
    # Show the candles and FVG zones
    print(f"\n📊 Candle Data:")
    for i, candle in enumerate(candles_ltf):
        print(f"   {i+1}. {candle['timestamp']}: {candle['low']:.2f} - {candle['high']:.2f} (Close: {candle['close']:.2f})")
    
    print(f"\n📊 Available FVG Pools:")
    relevant_fvgs = []
    for i, fvg in enumerate(fvg_pools):
        # Only show FVGs that might be relevant
        if fvg['zone_low'] < 110000 and fvg['zone_high'] > 105000:  # Price range filter
            relevant_fvgs.append(fvg)
            print(f"   {i+1}. {fvg['timestamp']}: {fvg['zone_low']:.2f} - {fvg['zone_high']:.2f} ({fvg['direction']})")
    
    print(f"\n🔍 Manual FVG Touch Check:")
    # Target FVG: 107161-107739
    target_fvg = None
    for fvg in fvg_pools:
        if abs(fvg['zone_low'] - 107161) < 10 and abs(fvg['zone_high'] - 107739) < 10:
            target_fvg = fvg
            break
    
    if target_fvg:
        print(f"   Target FVG: {target_fvg['timestamp']}")
        print(f"   Zone: {target_fvg['zone_low']:.2f} - {target_fvg['zone_high']:.2f}")
        print(f"   Direction: {target_fvg['direction']}")
        
        # Check which candles touch this FVG
        touching_candles = []
        for i, candle in enumerate(candles_ltf):
            if candle['low'] <= target_fvg['zone_high'] and candle['high'] >= target_fvg['zone_low']:
                touching_candles.append((i, candle))
        
        print(f"   Touching candles: {len(touching_candles)}")
        for i, (idx, candle) in enumerate(touching_candles):
            print(f"      {i+1}. Index {idx}: {candle['timestamp']}")
            print(f"         Range: {candle['low']:.2f} - {candle['high']:.2f}")
            print(f"         Overlap: {max(candle['low'], target_fvg['zone_low']):.2f} - {min(candle['high'], target_fvg['zone_high']):.2f}")
    else:
        print(f"   ❌ Target FVG not found in pools")
    
    print(f"\n🔍 Testing FVG Detector:")
    
    # Call detect_events
    try:
        fvg_events = fvg_detector.detect_events(candles_ltf, fvg_pools)
        print(f"   FVG Events Found: {len(fvg_events)}")
        
        for i, event in enumerate(fvg_events):
            print(f"   Event {i+1}: {event.timestamp} - {event.direction}")
            print(f"      Zone: {event.zone_low:.2f} - {event.zone_high:.2f}")
            print(f"      Touch Price: {event.touch_price:.2f}")
            
    except Exception as e:
        print(f"   ❌ Error in detect_events: {e}")
        import traceback
        traceback.print_exc()
    
    # Test with smaller subset
    print(f"\n🔍 Testing with 13:30 candle only:")
    
    # Find the 13:30 candle
    target_candle = None
    for candle in candles_ltf:
        if "13:30" in candle['timestamp']:
            target_candle = candle
            break
    
    if target_candle:
        print(f"   Target candle: {target_candle['timestamp']}")
        print(f"   Range: {target_candle['low']:.2f} - {target_candle['high']:.2f}")
        
        # Create minimal dataset
        minimal_candles = [target_candle]
        
        try:
            minimal_events = fvg_detector.detect_events(minimal_candles, fvg_pools)
            print(f"   Minimal Events Found: {len(minimal_events)}")
            
            for event in minimal_events:
                print(f"      Event: {event.timestamp} - {event.direction}")
                
        except Exception as e:
            print(f"   ❌ Error in minimal test: {e}")
    
    print(f"\n✅ Debug Complete!")
    db.close()


if __name__ == "__main__":
    debug_fvg_detection()
