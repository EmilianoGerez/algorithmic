#!/usr/bin/env python3
"""
Focused Test of Known FVG Touch at 13:30
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
import pandas as pd
from src.core.strategy.detectors.liquidity_pool_detectors import FVGPoolDetector
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


def test_focused_fvg_touch():
    """Test the specific FVG touch at 13:30"""
    
    print("🎯 Focused Test of Known FVG Touch at 13:30")
    print("=" * 60)
    
    # Initialize 
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    fvg_detector = FVGPoolDetector()
    
    # Get data for the specific time window (extended to get more candles)
    symbol = "BTC/USD"
    start = "2025-05-29T12:00:00Z"
    end = "2025-05-30T12:00:00Z"  # Extended to 24 hours
    
    print(f"📥 Getting data for {start} to {end}")
    
    # Get LTF data
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe="15T",
        start=start,
        end=end
    )
    ltf_candles = ltf_result["candles"]
    
    print(f"   • LTF Candles: {len(ltf_candles)}")
    
    # Now simulate chronological processing
    df = pd.DataFrame(ltf_candles)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Target the 13:30 candle specifically
    target_time = pd.to_datetime("2025-05-29T13:30:00Z", utc=True)
    
    print(f"\n🔍 Processing candle at {target_time}")
    
    # Find the 13:30 candle
    target_candle_idx = None
    for idx, candle in df.iterrows():
        if candle['timestamp'] == target_time:
            target_candle_idx = idx
            break
    
    if target_candle_idx is None:
        print(f"   ❌ Could not find candle at {target_time}")
        return
    
    print(f"   📍 Found candle at index {target_candle_idx}")
    
    # Get historical candles up to this point (simulating real-time)
    historical_candles = df[df['timestamp'] <= target_time].copy()
    
    # Convert timestamps back to strings for FVG detector
    historical_candles['timestamp'] = historical_candles['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    historical_candles = historical_candles.to_dict('records')
    
    print(f"   📊 Historical candles available: {len(historical_candles)}")
    
    # Get FVG pools that would be available at 13:30
    # Only FVGs created before 13:30
    all_pools = service.get_liquidity_pools(symbol, "4H", "all")
    fvg_pools = all_pools.get('fvg_pools', [])
    
    available_pools = []
    for pool in fvg_pools:
        pool_time = pd.to_datetime(pool['timestamp'], utc=True)
        if pool_time <= target_time:
            available_pools.append(pool)
    
    print(f"   📊 Available FVG pools at 13:30: {len(available_pools)}")
    
    # Show the pools that should be available
    print(f"   🎯 Available FVG pools:")
    for i, pool in enumerate(available_pools):
        print(f"      {i+1}. {pool['timestamp']}: {pool['zone_low']:.2f}-{pool['zone_high']:.2f} ({pool['direction']})")
    
    # Test FVG detection
    print(f"\n🔍 Testing FVG detection at 13:30...")
    
    try:
        fvg_events = fvg_detector.detect_events(historical_candles, available_pools)
        print(f"   📊 FVG events detected: {len(fvg_events)}")
        
        if fvg_events:
            print(f"   🎯 FVG events:")
            for i, event in enumerate(fvg_events):
                print(f"      {i+1}. {event.timestamp}: {event.zone_low:.2f}-{event.zone_high:.2f} ({event.direction})")
                
                # Check if this is the expected FVG (107161-107739)
                if abs(event.zone_low - 107161) < 10 and abs(event.zone_high - 107739) < 10:
                    print(f"         ✅ This is the expected FVG!")
                    
                    # Test swing point detection
                    print(f"         🔍 Testing swing point detection...")
                    
                    # Find event candle index
                    event_time = pd.to_datetime(event.timestamp, utc=True)
                    event_candle_idx = None
                    
                    for idx, candle in df.iterrows():
                        if candle['timestamp'] == event_time:
                            event_candle_idx = idx
                            break
                    
                    if event_candle_idx is not None:
                        print(f"         📍 Event candle index: {event_candle_idx}")
                        
                        # Look for swing point in next 3 candles
                        for swing_idx in range(event_candle_idx + 1, min(event_candle_idx + 4, len(df))):
                            swing_candle = df.iloc[swing_idx]
                            print(f"         Candle {swing_idx}: {swing_candle['timestamp']} - High: {swing_candle['high']:.2f}")
                            
                            # For bearish FVG, look for swing high
                            if event.direction == "bearish":
                                # Check if this could be a swing high
                                is_swing_high = True
                                current_high = swing_candle['high']
                                
                                # Check previous candle
                                if swing_idx > 0:
                                    prev_high = df.iloc[swing_idx - 1]['high']
                                    if current_high <= prev_high:
                                        is_swing_high = False
                                
                                # Check next candle if exists
                                if swing_idx < len(df) - 1:
                                    next_high = df.iloc[swing_idx + 1]['high']
                                    if current_high <= next_high:
                                        is_swing_high = False
                                
                                if is_swing_high:
                                    print(f"         ✅ Potential swing high at {swing_candle['timestamp']}: {current_high:.2f}")
                                    
                                    # Test EMA crossover after swing point
                                    print(f"         🔍 Testing EMA crossover after swing point...")
                                    
                                    # Get confirmation candles after swing
                                    confirmation_start = swing_idx + 1
                                    confirmation_candles = df.iloc[confirmation_start:].to_dict('records')
                                    
                                    print(f"         📊 Confirmation candles: {len(confirmation_candles)}")
                                    
                                    if len(confirmation_candles) >= 20:  # Need enough for EMA
                                        # Calculate EMAs
                                        conf_df = pd.DataFrame(confirmation_candles)
                                        conf_df['ema_9'] = conf_df['close'].ewm(span=9).mean()
                                        conf_df['ema_20'] = conf_df['close'].ewm(span=20).mean()
                                        
                                        # Look for bullish crossover (9 EMA crosses above 20 EMA)
                                        for j in range(1, len(conf_df)):
                                            prev_9 = conf_df.iloc[j-1]['ema_9']
                                            prev_20 = conf_df.iloc[j-1]['ema_20']
                                            curr_9 = conf_df.iloc[j]['ema_9']
                                            curr_20 = conf_df.iloc[j]['ema_20']
                                            
                                            if prev_9 <= prev_20 and curr_9 > curr_20:
                                                crossover_time = conf_df.iloc[j]['timestamp']
                                                crossover_price = conf_df.iloc[j]['close']
                                                print(f"         ✅ BULLISH EMA CROSSOVER at {crossover_time}: {crossover_price:.2f}")
                                                print(f"            EMA 9: {curr_9:.2f}, EMA 20: {curr_20:.2f}")
                                                
                                                print(f"         🎉 SIGNAL SHOULD BE GENERATED!")
                                                print(f"            FVG: {event.timestamp}")
                                                print(f"            Swing: {swing_candle['timestamp']}")
                                                print(f"            EMA: {crossover_time}")
                                                break
                                    else:
                                        print(f"         ❌ Not enough confirmation candles for EMA")
        else:
            print(f"   ❌ No FVG events detected")
            
    except Exception as e:
        print(f"   ❌ Error in FVG detection: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n✅ Focused test complete!")
    db.close()


if __name__ == "__main__":
    test_focused_fvg_touch()
