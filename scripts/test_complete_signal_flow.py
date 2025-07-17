#!/usr/bin/env python3
"""
Complete Test of FVG Touch → Swing Point → EMA Crossover
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


def test_complete_signal_flow():
    """Test the complete signal flow: FVG → Swing → EMA crossover"""
    
    print("🎯 Complete Signal Flow Test")
    print("=" * 60)
    
    # Initialize 
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Get extended data
    symbol = "BTC/USD"
    start = "2025-05-29T12:00:00Z"
    end = "2025-05-30T12:00:00Z"
    
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
    
    # Convert to DataFrame
    df = pd.DataFrame(ltf_candles)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Find the 13:30 candle (FVG touch)
    fvg_touch_time = pd.to_datetime("2025-05-29T13:30:00Z", utc=True)
    fvg_candle_idx = None
    
    for idx, candle in df.iterrows():
        if candle['timestamp'] == fvg_touch_time:
            fvg_candle_idx = idx
            break
    
    if fvg_candle_idx is None:
        print(f"❌ Could not find FVG touch candle at {fvg_touch_time}")
        return
    
    print(f"✅ Found FVG touch at index {fvg_candle_idx}")
    
    # Step 1: Detect swing point after FVG touch
    print(f"\n🔍 Step 1: Swing Point Detection")
    
    # For bearish FVG, look for swing high in next 3 candles
    swing_candle_idx = None
    swing_high = 0
    
    for idx in range(fvg_candle_idx + 1, min(fvg_candle_idx + 4, len(df))):
        candle = df.iloc[idx]
        print(f"   Candle {idx}: {candle['timestamp']} - High: {candle['high']:.2f}")
        
        if candle['high'] > swing_high:
            swing_high = candle['high']
            swing_candle_idx = idx
    
    if swing_candle_idx is None:
        print(f"❌ No swing point found")
        return
    
    swing_candle = df.iloc[swing_candle_idx]
    print(f"✅ Swing high found at index {swing_candle_idx}: {swing_candle['timestamp']} - {swing_high:.2f}")
    
    # Step 2: Look for EMA crossover after swing point
    print(f"\n🔍 Step 2: EMA Crossover Detection")
    
    # Get confirmation candles after swing point
    confirmation_start = swing_candle_idx + 1
    confirmation_end = len(df)
    
    if confirmation_start >= confirmation_end:
        print(f"❌ No confirmation candles after swing point")
        return
    
    confirmation_candles = df.iloc[confirmation_start:confirmation_end]
    print(f"   📊 Confirmation candles: {len(confirmation_candles)}")
    
    if len(confirmation_candles) < 20:
        print(f"❌ Not enough confirmation candles for EMA calculation")
        return
    
    # Calculate EMAs
    confirmation_candles = confirmation_candles.copy()
    confirmation_candles['ema_9'] = confirmation_candles['close'].ewm(span=9).mean()
    confirmation_candles['ema_20'] = confirmation_candles['close'].ewm(span=20).mean()
    
    print(f"   📊 EMA calculation complete")
    
    # Look for bullish crossover (9 EMA crosses above 20 EMA)
    crossover_found = False
    
    for i in range(1, len(confirmation_candles)):
        current_row = confirmation_candles.iloc[i]
        previous_row = confirmation_candles.iloc[i-1]
        
        prev_9 = previous_row['ema_9']
        prev_20 = previous_row['ema_20']
        curr_9 = current_row['ema_9']
        curr_20 = current_row['ema_20']
        
        # Check for bullish crossover
        if prev_9 <= prev_20 and curr_9 > curr_20:
            crossover_time = current_row['timestamp']
            crossover_price = current_row['close']
            
            print(f"   ✅ BULLISH EMA CROSSOVER FOUND!")
            print(f"      Time: {crossover_time}")
            print(f"      Price: {crossover_price:.2f}")
            print(f"      EMA 9: {curr_9:.2f}")
            print(f"      EMA 20: {curr_20:.2f}")
            print(f"      Separation: {curr_9 - curr_20:.2f}")
            
            # Calculate timing
            fvg_time = df.iloc[fvg_candle_idx]['timestamp']
            swing_time = df.iloc[swing_candle_idx]['timestamp']
            
            fvg_to_swing = (swing_time - fvg_time).total_seconds() / 3600
            swing_to_ema = (crossover_time - swing_time).total_seconds() / 3600
            total_time = (crossover_time - fvg_time).total_seconds() / 3600
            
            print(f"      Timing:")
            print(f"         FVG → Swing: {fvg_to_swing:.1f} hours")
            print(f"         Swing → EMA: {swing_to_ema:.1f} hours")
            print(f"         Total: {total_time:.1f} hours")
            
            crossover_found = True
            break
    
    if not crossover_found:
        print(f"❌ No bullish EMA crossover found")
        
        # Show EMA status at the end
        last_candle = confirmation_candles.iloc[-1]
        print(f"   📊 Final EMA status:")
        print(f"      EMA 9: {last_candle['ema_9']:.2f}")
        print(f"      EMA 20: {last_candle['ema_20']:.2f}")
        print(f"      Difference: {last_candle['ema_9'] - last_candle['ema_20']:.2f}")
        
        # Check if EMAs are converging
        first_diff = confirmation_candles.iloc[19]['ema_9'] - confirmation_candles.iloc[19]['ema_20']
        last_diff = last_candle['ema_9'] - last_candle['ema_20']
        
        print(f"      Convergence: {first_diff:.2f} → {last_diff:.2f}")
        
        if last_diff > first_diff:
            print(f"      📈 EMAs are converging - crossover may happen later")
        else:
            print(f"      📉 EMAs are diverging - crossover unlikely")
    
    # Step 3: Summary
    print(f"\n📊 Summary:")
    print(f"   • FVG Touch: ✅ {fvg_touch_time}")
    print(f"   • Swing Point: ✅ {swing_candle['timestamp']} at {swing_high:.2f}")
    print(f"   • EMA Crossover: {'✅' if crossover_found else '❌'}")
    
    if crossover_found:
        print(f"   🎉 COMPLETE SIGNAL CHAIN FOUND!")
        print(f"      This should generate a signal in our strategy!")
    else:
        print(f"   ⚠️ Signal chain incomplete - no EMA crossover")
        print(f"      Strategy would not generate a signal")
    
    print(f"\n✅ Complete test finished!")
    db.close()


if __name__ == "__main__":
    test_complete_signal_flow()
