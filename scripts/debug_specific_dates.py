#!/usr/bin/env python3
"""
Debug Time-Aware Strategy for Specific Dates
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


def debug_specific_dates():
    """Debug specific dates mentioned by user"""
    
    print("🔍 Debug Specific Dates for Signal Detection")
    print("=" * 60)
    
    # Initialize dependencies
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Parameters
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    start = "2025-05-25T00:00:00Z"
    end = "2025-06-05T00:00:00Z"
    
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
    
    df = pd.DataFrame(candles_ltf)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp')
    
    print(f"   • LTF Candles: {len(candles_ltf)}")
    print(f"   • HTF FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
    
    # Target times to investigate
    target_times = [
        "2025-05-27T03:00:00Z",  # May 27 around 3:00 AM
        "2025-06-01T09:30:00Z",  # Jun 1 around 9:30 AM  
        "2025-06-03T09:30:00Z",  # Jun 3 around 9:30 AM
    ]
    
    fvg_detector = FVGPoolDetector()
    
    for target_time in target_times:
        print(f"\n🎯 Investigating {target_time}")
        print("-" * 50)
        
        target_dt = pd.to_datetime(target_time, utc=True)
        
        # Find candles around this time
        window_start = target_dt - pd.Timedelta(hours=2)
        window_end = target_dt + pd.Timedelta(hours=2)
        
        window_candles = df[
            (df['timestamp'] >= window_start) & 
            (df['timestamp'] <= window_end)
        ]
        
        print(f"📊 Window Analysis ({window_start} to {window_end}):")
        print(f"   • Candles in window: {len(window_candles)}")
        
        if len(window_candles) == 0:
            print("   ❌ No candles in target window")
            continue
        
        # Show price action around target time
        print(f"   • Price action around {target_time}:")
        for idx, row in window_candles.iterrows():
            if abs((row['timestamp'] - target_dt).total_seconds()) <= 1800:  # Within 30 minutes
                print(f"     {row['timestamp']}: O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f}")
        
        # Check which FVGs would be active at this time
        print(f"   • FVGs active at {target_time}:")
        active_fvgs = []
        
        for fvg in htf_pools.get('fvg_pools', []):
            fvg_creation_time = pd.to_datetime(fvg['timestamp'], utc=True)
            
            # Only FVGs created before target time
            if fvg_creation_time <= target_dt:
                # Within 72 hours
                time_diff = (target_dt - fvg_creation_time).total_seconds() / 3600
                if time_diff <= 72:
                    active_fvgs.append(fvg)
                    high_val = fvg.get('high', fvg.get('upper_bound', 'N/A'))
                    low_val = fvg.get('low', fvg.get('lower_bound', 'N/A'))
                    print(f"     • {fvg['timestamp']} - {fvg.get('direction', 'unknown')} - "
                          f"Age: {time_diff:.1f}h - High: {high_val} Low: {low_val}")
                    print(f"       FVG keys: {list(fvg.keys())}")  # Debug FVG structure
        
        if not active_fvgs:
            print("   ❌ No active FVGs at this time")
            continue
        
        # Check for FVG interactions
        print(f"   • Checking FVG interactions...")
        historical_candles = df[df['timestamp'] <= target_dt].tail(200).to_dict('records')
        
        try:
            fvg_events = fvg_detector.detect_events(historical_candles, active_fvgs)
            
            recent_events = [
                event for event in fvg_events 
                if abs((target_dt - pd.to_datetime(event.timestamp, utc=True)).total_seconds()) <= 7200  # Within 2 hours
            ]
            
            print(f"   • FVG events near {target_time}: {len(recent_events)}")
            
            for event in recent_events:
                print(f"     • {event.timestamp}: {event.pool_type.value} {event.status} - "
                      f"Price: ${event.price:.2f} - Direction: {event.direction.value}")
            
            if recent_events:
                # Check for EMA crossovers around this time
                print(f"   • Checking EMA crossovers...")
                
                # Calculate EMAs for window
                window_candles_copy = window_candles.copy()
                window_candles_copy['ema_fast'] = window_candles_copy['close'].ewm(span=9).mean()
                window_candles_copy['ema_slow'] = window_candles_copy['close'].ewm(span=20).mean()
                
                # Detect crossovers
                window_candles_copy['ema_fast_above'] = window_candles_copy['ema_fast'] > window_candles_copy['ema_slow']
                window_candles_copy['ema_cross'] = window_candles_copy['ema_fast_above'] != window_candles_copy['ema_fast_above'].shift(1)
                
                crossovers = window_candles_copy[window_candles_copy['ema_cross'] & window_candles_copy['ema_cross'].notna()]
                
                print(f"   • EMA crossovers in window: {len(crossovers)}")
                
                for idx, row in crossovers.iterrows():
                    direction = 'Bullish' if row['ema_fast_above'] else 'Bearish'
                    print(f"     • {row['timestamp']}: {direction} - "
                          f"EMA9: {row['ema_fast']:.2f} EMA20: {row['ema_slow']:.2f}")
                
        except Exception as e:
            print(f"   ❌ Error checking FVG events: {e}")
    
    print(f"\n✅ Debug Complete!")
    db.close()


if __name__ == "__main__":
    debug_specific_dates()
