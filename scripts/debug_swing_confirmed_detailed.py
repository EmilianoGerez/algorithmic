#!/usr/bin/env python3
"""
Debug Swing Confirmed Strategy Step by Step
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
from src.core.strategy.detectors.liquidity_pool_detectors import FVGPoolDetector


def debug_swing_confirmed_strategy():
    """Debug each step of the swing confirmed strategy"""
    
    print("🔍 Debug Swing Confirmed Strategy")
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
    
    # Get first FVG pool
    fvg_pools = htf_pools.get('fvg_pools', [])[:3]
    
    if not fvg_pools:
        print("❌ No FVG pools found")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(candles_ltf)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Detect FVG events
    fvg_detector = FVGPoolDetector()
    fvg_events = fvg_detector.detect_events(candles_ltf, fvg_pools)
    
    print(f"   • FVG Events: {len(fvg_events)}")
    
    if not fvg_events:
        print("❌ No FVG events found")
        return
    
    # Debug first FVG event
    fvg_event = fvg_events[0]
    print(f"\n🎯 Debugging FVG Event:")
    print(f"   • Timestamp: {fvg_event.timestamp}")
    print(f"   • Direction: {fvg_event.direction.value}")
    print(f"   • Status: {fvg_event.status}")
    print(f"   • Price: ${fvg_event.price:.2f}")
    
    # Step 1: Find the FVG touch candle
    fvg_time = pd.to_datetime(fvg_event.timestamp, utc=True)
    candle_idx = df[df['timestamp'] == fvg_time].index
    
    if len(candle_idx) == 0:
        print("❌ Could not find FVG touch candle in dataset")
        return
    
    candle_idx = candle_idx[0]
    print(f"\n📍 Step 1 - FVG Touch Candle:")
    print(f"   • Candle Index: {candle_idx}")
    print(f"   • Timestamp: {df.iloc[candle_idx]['timestamp']}")
    print(f"   • OHLC: O:{df.iloc[candle_idx]['open']:.2f}, H:{df.iloc[candle_idx]['high']:.2f}, L:{df.iloc[candle_idx]['low']:.2f}, C:{df.iloc[candle_idx]['close']:.2f}")
    
    # Step 2: Look for swing point formation (next 2-3 candles)
    swing_lookback = 3
    swing_start_idx = candle_idx + 1
    swing_end_idx = min(candle_idx + swing_lookback + 1, len(df))
    
    print(f"\n📈 Step 2 - Swing Point Detection:")
    print(f"   • Looking at candles {swing_start_idx} to {swing_end_idx-1}")
    print(f"   • FVG Direction: {fvg_event.direction.value}")
    
    if swing_end_idx >= len(df):
        print("❌ Not enough candles after FVG touch")
        return
    
    # Show the swing candles
    swing_candles = df.iloc[swing_start_idx:swing_end_idx]
    print(f"   • Swing Candles:")
    for i, row in swing_candles.iterrows():
        print(f"     {i-candle_idx}: {row['timestamp']} - Close: ${row['close']:.2f}")
    
    # Check swing formation
    if len(swing_candles) < 2:
        print("❌ Not enough swing candles")
        return
    
    closes = swing_candles['close'].values
    swing_detected = False
    
    if fvg_event.direction.value == 'bullish':
        # For bullish FVG, look for higher closes (bounce)
        if closes[-1] > closes[0]:
            swing_detected = True
            swing_strength = (closes[-1] - closes[0]) / closes[0]
            print(f"   ✅ Bullish swing detected!")
            print(f"   • Swing strength: {swing_strength:.4f} ({swing_strength*100:.2f}%)")
    
    elif fvg_event.direction.value == 'bearish':
        # For bearish FVG, look for lower closes (rejection)
        if closes[-1] < closes[0]:
            swing_detected = True
            swing_strength = (closes[0] - closes[-1]) / closes[0]
            print(f"   ✅ Bearish swing detected!")
            print(f"   • Swing strength: {swing_strength:.4f} ({swing_strength*100:.2f}%)")
    
    if not swing_detected:
        print(f"   ❌ No swing detected")
        print(f"   • First close: ${closes[0]:.2f}")
        print(f"   • Last close: ${closes[-1]:.2f}")
        print(f"   • Expected: {'higher' if fvg_event.direction.value == 'bullish' else 'lower'} closes")
        return
    
    # Step 3: Look for EMA crossover within extended window
    confirmation_window_hours = 12  # Extended window
    confirmation_end_time = fvg_time + pd.Timedelta(hours=confirmation_window_hours)
    
    print(f"\n📊 Step 3 - EMA Crossover Detection:")
    print(f"   • Confirmation Window: {fvg_time} to {confirmation_end_time}")
    
    # Get candles in confirmation window
    confirmation_mask = (df['timestamp'] >= fvg_time) & (df['timestamp'] <= confirmation_end_time)
    confirmation_candles = df[confirmation_mask].copy()
    
    print(f"   • Confirmation Candles: {len(confirmation_candles)}")
    
    if len(confirmation_candles) < 30:
        print("❌ Not enough candles for EMA calculation")
        return
    
    # Calculate EMAs
    fast_period = 9
    slow_period = 20
    
    confirmation_candles['ema_fast'] = confirmation_candles['close'].ewm(span=fast_period).mean()
    confirmation_candles['ema_slow'] = confirmation_candles['close'].ewm(span=slow_period).mean()
    
    # Detect crossovers
    confirmation_candles['ema_fast_above'] = confirmation_candles['ema_fast'] > confirmation_candles['ema_slow']
    confirmation_candles['ema_cross'] = confirmation_candles['ema_fast_above'] != confirmation_candles['ema_fast_above'].shift(1)
    
    crossovers = confirmation_candles[confirmation_candles['ema_cross'] & confirmation_candles['ema_cross'].notna()]
    
    print(f"   • Total EMA Crossovers: {len(crossovers)}")
    
    if len(crossovers) == 0:
        print("   ❌ No EMA crossovers in confirmation window")
        return
    
    # Show all crossovers
    print(f"   • Crossover Details:")
    expected_direction = fvg_event.direction.value
    matching_crossover = None
    
    for idx, row in crossovers.iterrows():
        crossover_direction = 'bullish' if row['ema_fast_above'] else 'bearish'
        print(f"     - {row['timestamp']}: {crossover_direction} crossover")
        print(f"       EMA Fast: {row['ema_fast']:.2f}, EMA Slow: {row['ema_slow']:.2f}")
        print(f"       Price: ${row['close']:.2f}")
        
        if crossover_direction == expected_direction:
            matching_crossover = row
            print(f"       ✅ MATCHES expected direction ({expected_direction})")
        else:
            print(f"       ❌ Wrong direction (expected {expected_direction})")
    
    if matching_crossover is not None:
        print(f"\n🎉 ALL CONDITIONS MET!")
        print(f"   1. ✅ FVG Touch: {fvg_event.timestamp}")
        print(f"   2. ✅ Swing Point: {fvg_event.direction.value}")
        print(f"   3. ✅ EMA Crossover: {matching_crossover['timestamp']}")
        print(f"   → Signal would be generated!")
        
        # Calculate confidence
        ema_separation = abs(matching_crossover['ema_fast'] - matching_crossover['ema_slow']) / matching_crossover['close']
        confidence = min(0.95, 0.5 + swing_strength * 10 + ema_separation * 100)
        print(f"   → Confidence: {confidence:.2f}")
    else:
        print(f"\n❌ No matching EMA crossover found")
        print(f"   Expected: {expected_direction}")
        print(f"   Found: {[('bullish' if row['ema_fast_above'] else 'bearish') for idx, row in crossovers.iterrows()]}")
    
    print(f"\n✅ Debug Complete!")
    db.close()


if __name__ == "__main__":
    debug_swing_confirmed_strategy()
