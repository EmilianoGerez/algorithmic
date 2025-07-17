#!/usr/bin/env python3
"""
Debug Signal Processing After FVG Events
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
import pandas as pd
from src.core.strategy.swing_confirmed_ema_strategy import SwingConfirmedEMACrossoverStrategy
from src.core.strategy.detectors.liquidity_pool_detectors import FVGPoolDetector
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


def debug_signal_processing():
    """Debug what happens after FVG events are detected"""
    
    print("🔍 Debugging Signal Processing After FVG Events")
    print("=" * 60)
    
    # Initialize 
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    strategy = SwingConfirmedEMACrossoverStrategy()
    fvg_detector = FVGPoolDetector()
    
    # Focus on May 29 13:30 when we know FVG touch occurred
    symbol = "BTC/USD"
    start = "2025-05-29T13:00:00Z"
    end = "2025-05-29T16:00:00Z"
    
    print(f"📥 Getting data for {start} to {end}")
    
    # Get data
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe="15T",
        start=start,
        end=end
    )
    candles_ltf = ltf_result["candles"]
    
    htf_pools = service.get_liquidity_pools(symbol, "4H", "all")
    fvg_pools = htf_pools.get('fvg_pools', [])
    
    print(f"   • LTF Candles: {len(candles_ltf)}")
    print(f"   • HTF FVG Pools: {len(fvg_pools)}")
    
    # Get FVG events
    fvg_events = fvg_detector.detect_events(candles_ltf, fvg_pools)
    print(f"   • FVG Events: {len(fvg_events)}")
    
    # Test each step of the strategy
    if fvg_events:
        print(f"\n🔍 Processing FVG Events:")
        
        for i, fvg_event in enumerate(fvg_events[:3]):  # Test first 3 events
            print(f"\n--- Event {i+1}: {fvg_event.timestamp} ({fvg_event.direction}) ---")
            print(f"   Zone: {fvg_event.zone_low:.2f} - {fvg_event.zone_high:.2f}")
            
            # Convert to DataFrame
            df = pd.DataFrame(candles_ltf)
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Find FVG candle index
            fvg_candle_idx = None
            fvg_time = pd.to_datetime(fvg_event.timestamp, utc=True)
            
            for idx, candle in df.iterrows():
                if candle['timestamp'] == fvg_time:
                    fvg_candle_idx = idx
                    break
            
            if fvg_candle_idx is None:
                print(f"   ❌ Could not find FVG candle in DataFrame")
                continue
            
            print(f"   📍 FVG Candle Index: {fvg_candle_idx}")
            
            # Step 1: Check swing point detection
            print(f"   🔍 Step 1: Swing Point Detection")
            swing_point = strategy._detect_swing_point(df, fvg_candle_idx, fvg_event.direction)
            
            if swing_point:
                print(f"      ✅ Swing point found: {swing_point['timestamp']} at {swing_point['price']:.2f}")
                print(f"      Swing properties: {list(swing_point.keys())}")
                
                # Step 2: Check EMA crossover
                print(f"   🔍 Step 2: EMA Crossover Detection")
                
                # Find swing point candle index
                swing_time = pd.to_datetime(swing_point['timestamp'], utc=True)
                swing_candle_idx = None
                
                for idx, candle in df.iterrows():
                    if candle['timestamp'] == swing_time:
                        swing_candle_idx = idx
                        break
                
                if swing_candle_idx is None:
                    print(f"      ❌ Could not find swing candle in DataFrame")
                    continue
                
                # Get confirmation candles
                confirmation_start = swing_candle_idx + 1
                confirmation_end = min(confirmation_start + 16, len(df))  # 4H window
                
                if confirmation_end <= len(df):
                    confirmation_candles = df.iloc[confirmation_start:confirmation_end].to_dict('records')
                    print(f"      Confirmation candles: {len(confirmation_candles)}")
                    
                    ema_crossover = strategy._find_ema_crossover(confirmation_candles, fvg_event.direction)
                    
                    if ema_crossover:
                        print(f"      ✅ EMA crossover found: {ema_crossover['timestamp']}")
                        print(f"      Direction: {ema_crossover['direction']}")
                        print(f"      Price: {ema_crossover['price']:.2f}")
                        print(f"      EMA Fast: {ema_crossover['ema_fast']:.2f}")
                        print(f"      EMA Slow: {ema_crossover['ema_slow']:.2f}")
                        
                        # Step 3: Check confidence calculation
                        print(f"   🔍 Step 3: Confidence Calculation")
                        confidence = strategy._calculate_confidence(swing_point, ema_crossover, fvg_event)
                        print(f"      Confidence: {confidence:.2f}")
                        
                        if confidence >= strategy.min_confidence:
                            print(f"      ✅ Confidence above threshold ({strategy.min_confidence})")
                            print(f"      🎯 This should generate a signal!")
                        else:
                            print(f"      ❌ Confidence below threshold ({strategy.min_confidence})")
                    else:
                        print(f"      ❌ No EMA crossover found")
                else:
                    print(f"      ❌ Not enough confirmation candles")
            else:
                print(f"      ❌ No swing point found")
    else:
        print(f"   ❌ No FVG events to process")
    
    print(f"\n✅ Debug Complete!")
    db.close()


if __name__ == "__main__":
    debug_signal_processing()
