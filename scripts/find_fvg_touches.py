#!/usr/bin/env python3
"""
Find When Price Actually Touched FVG Zones
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


def find_fvg_touch_times():
    """Find when price actually touched FVG zones"""
    
    print("🔍 Finding When Price Actually Touched FVG Zones")
    print("=" * 60)
    
    # Initialize dependencies
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Extended period to catch FVG touches
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    start = "2025-05-15T00:00:00Z"
    end = "2025-06-15T00:00:00Z"
    
    # Get data
    print(f"📥 Loading Data for {start} to {end}...")
    htf_pools = service.get_liquidity_pools(symbol, htf, "all")
    
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe=ltf,
        start=start,
        end=end
    )
    candles_ltf = ltf_result["candles"]
    
    df = pd.DataFrame(candles_ltf)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp')
    
    print(f"   • LTF Candles: {len(candles_ltf)}")
    print(f"   • HTF FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
    
    # Focus on the two bearish FVGs from May 29
    target_fvgs = [
        {
            'timestamp': '2025-05-29T12:00:00',
            'high': 107739.437,
            'low': 107161.277,
            'direction': 'bearish'
        },
        {
            'timestamp': '2025-05-29T16:00:00',
            'high': 106604.392610837,
            'low': 106486.615,
            'direction': 'bearish'
        }
    ]
    
    print(f"\n🎯 Target FVGs:")
    for i, fvg in enumerate(target_fvgs):
        print(f"   {i+1}. {fvg['timestamp']} - {fvg['direction']}")
        print(f"      Zone: {fvg['low']:.2f} - {fvg['high']:.2f}")
    
    # Find when price touched these zones
    print(f"\n🔍 Searching for FVG touches...")
    
    for i, fvg in enumerate(target_fvgs):
        print(f"\n--- FVG #{i+1}: {fvg['timestamp']} ---")
        print(f"Zone: {fvg['low']:.2f} - {fvg['high']:.2f}")
        
        # Find candles that touched this FVG
        touches = []
        
        # Only check candles after FVG creation
        fvg_creation_time = pd.to_datetime(fvg['timestamp'], utc=True)
        candles_after_fvg = df[df['timestamp'] > fvg_creation_time]
        
        for idx, candle in candles_after_fvg.iterrows():
            # Check if candle touched FVG zone
            if candle['low'] <= fvg['high'] and candle['high'] >= fvg['low']:
                touches.append({
                    'timestamp': candle['timestamp'],
                    'open': candle['open'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'close': candle['close']
                })
        
        print(f"Touches found: {len(touches)}")
        
        if touches:
            print(f"Touch Details:")
            for j, touch in enumerate(touches[:10]):  # Show first 10 touches
                print(f"   {j+1}. {touch['timestamp']}")
                print(f"      OHLC: {touch['open']:.2f} {touch['high']:.2f} {touch['low']:.2f} {touch['close']:.2f}")
                
                # Check if this is around the times user mentioned
                touch_time = touch['timestamp']
                
                # Check if near user-mentioned times
                user_times = [
                    pd.to_datetime("2025-05-27T03:00:00Z", utc=True),
                    pd.to_datetime("2025-06-01T09:30:00Z", utc=True),
                    pd.to_datetime("2025-06-03T09:30:00Z", utc=True)
                ]
                
                for user_time in user_times:
                    time_diff = abs((touch_time - user_time).total_seconds()) / 3600
                    if time_diff <= 12:  # Within 12 hours
                        print(f"      ⭐ Near user-mentioned time: {user_time} (diff: {time_diff:.1f}h)")
        else:
            print("   ❌ No touches found for this FVG")
    
    # Check price ranges during user-mentioned times
    print(f"\n📊 Price Ranges During User-Mentioned Times:")
    
    user_times = [
        "2025-05-27T03:00:00Z",
        "2025-06-01T09:30:00Z",
        "2025-06-03T09:30:00Z"
    ]
    
    for user_time in user_times:
        user_dt = pd.to_datetime(user_time, utc=True)
        
        # Find nearest candle
        nearest_candle = df.iloc[(df['timestamp'] - user_dt).abs().argsort()[:1]]
        
        if not nearest_candle.empty:
            candle = nearest_candle.iloc[0]
            print(f"\n{user_time}:")
            print(f"   Price Range: {candle['low']:.2f} - {candle['high']:.2f}")
            print(f"   Close: {candle['close']:.2f}")
            
            # Check distance to FVG zones
            for fvg in target_fvgs:
                distance_to_zone = min(
                    abs(candle['close'] - fvg['low']),
                    abs(candle['close'] - fvg['high'])
                )
                print(f"   Distance to {fvg['timestamp']} FVG: {distance_to_zone:.2f} points")
    
    print(f"\n✅ Analysis Complete!")
    db.close()


if __name__ == "__main__":
    find_fvg_touch_times()
