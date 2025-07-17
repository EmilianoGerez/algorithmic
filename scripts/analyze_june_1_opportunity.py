#!/usr/bin/env python3
"""
Deep Analysis of June 1 Signal Opportunity
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


def analyze_june_1_opportunity():
    """Deep analysis of June 1 signal opportunity"""
    
    print("🔍 Deep Analysis: June 1, 2025 Signal Opportunity")
    print("=" * 70)
    
    # Initialize dependencies
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Parameters - focus on June 1
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    start = "2025-05-31T00:00:00Z"
    end = "2025-06-02T00:00:00Z"
    
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
    
    # Target time
    target_time = "2025-06-01T09:30:00Z"
    target_dt = pd.to_datetime(target_time, utc=True)
    
    print(f"\n🎯 Analyzing {target_time}")
    print("-" * 50)
    
    # Find active FVGs
    print(f"📊 Active FVGs at {target_time}:")
    active_fvgs = []
    
    for fvg in htf_pools.get('fvg_pools', []):
        fvg_creation_time = pd.to_datetime(fvg['timestamp'], utc=True)
        
        if fvg_creation_time <= target_dt:
            time_diff = (target_dt - fvg_creation_time).total_seconds() / 3600
            if time_diff <= 72:  # Within 72 hours
                active_fvgs.append(fvg)
                print(f"   • {fvg['timestamp']} - {fvg.get('direction', 'unknown')}")
                print(f"     Age: {time_diff:.1f}h")
                print(f"     Zone: {fvg.get('zone_low', 'N/A')} - {fvg.get('zone_high', 'N/A')}")
                print(f"     Status: {fvg.get('status', 'unknown')}")
                print()
    
    if not active_fvgs:
        print("   ❌ No active FVGs found")
        return
    
    # Check price action around target time
    print(f"📈 Price Action Around {target_time}:")
    window_start = target_dt - pd.Timedelta(hours=3)
    window_end = target_dt + pd.Timedelta(hours=3)
    
    window_candles = df[
        (df['timestamp'] >= window_start) & 
        (df['timestamp'] <= window_end)
    ]
    
    print(f"   6-hour window: {len(window_candles)} candles")
    
    # Show key price levels
    for idx, row in window_candles.iterrows():
        if row['timestamp'] == target_dt or abs((row['timestamp'] - target_dt).total_seconds()) <= 900:  # Within 15 minutes
            print(f"   • {row['timestamp']}: "
                  f"O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f}")
    
    # Test FVG interactions manually
    print(f"\n🔍 Testing FVG Interactions:")
    
    # Prepare data for FVG detector
    fvg_detector = FVGPoolDetector()
    
    # Convert FVGs to expected format
    formatted_fvgs = []
    for fvg in active_fvgs:
        try:
            # Try to format FVG data properly
            formatted_fvg = {
                'timestamp': fvg['timestamp'],
                'high': float(fvg.get('zone_high', 0)),
                'low': float(fvg.get('zone_low', 0)),
                'direction': fvg.get('direction', 'unknown'),
                'status': fvg.get('status', 'open')
            }
            formatted_fvgs.append(formatted_fvg)
            print(f"   • Formatted FVG: {formatted_fvg}")
        except Exception as e:
            print(f"   ❌ Error formatting FVG: {e}")
    
    if formatted_fvgs:
        try:
            # Test FVG interactions
            historical_candles = df[df['timestamp'] <= target_dt].tail(100).to_dict('records')
            
            print(f"\n🔍 Testing with {len(historical_candles)} historical candles...")
            
            # Create a simple FVG interaction test
            target_candle = window_candles[window_candles['timestamp'] == target_dt]
            
            if not target_candle.empty:
                candle = target_candle.iloc[0]
                
                print(f"   • Target candle: {target_dt}")
                print(f"     OHLC: {candle['open']:.2f} {candle['high']:.2f} {candle['low']:.2f} {candle['close']:.2f}")
                
                # Check if price touched any FVG
                for fvg in formatted_fvgs:
                    fvg_high = fvg['high']
                    fvg_low = fvg['low']
                    
                    # Check if candle interacted with FVG
                    if candle['low'] <= fvg_high and candle['high'] >= fvg_low:
                        print(f"     ✅ TOUCHED FVG: {fvg['timestamp']} ({fvg['direction']})")
                        print(f"       FVG Zone: {fvg_low:.2f} - {fvg_high:.2f}")
                        print(f"       Candle Range: {candle['low']:.2f} - {candle['high']:.2f}")
                        
                        # Check for EMA crossover around this time
                        print(f"\n📊 EMA Analysis:")
                        
                        # Calculate EMAs for window
                        window_copy = window_candles.copy()
                        window_copy['ema_fast'] = window_copy['close'].ewm(span=9).mean()
                        window_copy['ema_slow'] = window_copy['close'].ewm(span=20).mean()
                        
                        # Find EMA values at target time
                        target_ema = window_copy[window_copy['timestamp'] == target_dt]
                        
                        if not target_ema.empty:
                            ema_row = target_ema.iloc[0]
                            print(f"       EMA9: {ema_row['ema_fast']:.2f}")
                            print(f"       EMA20: {ema_row['ema_slow']:.2f}")
                            print(f"       EMA9 > EMA20: {ema_row['ema_fast'] > ema_row['ema_slow']}")
                            
                            # Check for crossovers in window
                            window_copy['ema_fast_above'] = window_copy['ema_fast'] > window_copy['ema_slow']
                            window_copy['ema_cross'] = window_copy['ema_fast_above'] != window_copy['ema_fast_above'].shift(1)
                            
                            crossovers = window_copy[window_copy['ema_cross'] & window_copy['ema_cross'].notna()]
                            
                            print(f"       EMA Crossovers in 6h window: {len(crossovers)}")
                            
                            for idx, cross_row in crossovers.iterrows():
                                direction = 'Bullish' if cross_row['ema_fast_above'] else 'Bearish'
                                print(f"         • {cross_row['timestamp']}: {direction}")
                                
                                # Check if crossover matches FVG direction
                                if fvg['direction'] == 'bearish' and direction == 'Bearish':
                                    print(f"           ✅ DIRECTION MATCH! Bearish FVG + Bearish EMA crossover")
                                elif fvg['direction'] == 'bullish' and direction == 'Bullish':
                                    print(f"           ✅ DIRECTION MATCH! Bullish FVG + Bullish EMA crossover")
                                else:
                                    print(f"           ❌ Direction mismatch: {fvg['direction']} FVG vs {direction} crossover")
                        
                        print()
                        
        except Exception as e:
            print(f"   ❌ Error testing FVG interactions: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ Analysis Complete!")
    db.close()


if __name__ == "__main__":
    analyze_june_1_opportunity()
