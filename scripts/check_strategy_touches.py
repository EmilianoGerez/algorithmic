#!/usr/bin/env python3
"""
Check Strategy Performance During Actual FVG Touches
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
import pandas as pd
from src.core.strategy.time_aware_fvg_strategy import TimeAwareFVGStrategy
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


def check_strategy_during_touches():
    """Check if strategy worked during actual FVG touches"""
    
    print("🎯 Checking Strategy During Actual FVG Touches")
    print("=" * 60)
    
    # Initialize strategy
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    strategy = TimeAwareFVGStrategy()
    
    # Initialize service for data fetching
    from src.services.signal_detection import SignalDetectionService
    service = SignalDetectionService(repo, redis, db)
    
    # Focus on specific FVG touch periods
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    
    # Test periods when FVG touches occurred
    test_periods = [
        {
            "name": "May 29 - FVG #1 First Touch",
            "start": "2025-05-29T13:00:00Z",
            "end": "2025-05-29T16:00:00Z",
            "expected_fvg": "107161-107739"
        },
        {
            "name": "May 29 - FVG #2 First Touch", 
            "start": "2025-05-29T17:00:00Z",
            "end": "2025-05-29T20:00:00Z",
            "expected_fvg": "106486-106604"
        },
        {
            "name": "June 3 - FVG #2 Touch (User mentioned)",
            "start": "2025-06-03T01:00:00Z",
            "end": "2025-06-03T04:00:00Z",
            "expected_fvg": "106486-106604"
        },
        {
            "name": "June 3 - FVG #2 Touch Afternoon",
            "start": "2025-06-03T14:00:00Z",
            "end": "2025-06-03T17:00:00Z",
            "expected_fvg": "106486-106604"
        }
    ]
    
    for period in test_periods:
        print(f"\n🔍 Testing: {period['name']}")
        print(f"   Period: {period['start']} to {period['end']}")
        print(f"   Expected FVG: {period['expected_fvg']}")
        
        try:
            # Get data for this period
            ltf_result = service.detect_signals(
                symbol=symbol,
                signal_type="fvg_and_pivot",
                timeframe=ltf,
                start=period['start'],
                end=period['end']
            )
            candles_ltf = ltf_result["candles"]
            
            htf_pools = service.get_liquidity_pools(symbol, htf, "all")
            
            # Run strategy for this period
            signals = strategy.generate_signals(
                candles_ltf=candles_ltf,
                htf_pools=htf_pools
            )
            
            print(f"   📊 Signals Generated: {len(signals)}")
            
            if signals:
                for i, signal in enumerate(signals):
                    print(f"   ✅ Signal {i+1}:")
                    print(f"      • Time: {signal['timestamp']}")
                    print(f"      • Price: {signal['price']}")
                    print(f"      • Direction: {signal['direction']}")
                    print(f"      • FVG Zone: {signal['fvg_zone_low']:.2f} - {signal['fvg_zone_high']:.2f}")
                    print(f"      • Confidence: {signal['confidence']:.2f}")
                    print(f"      • Swing Price: {signal['swing_price']:.2f}")
                    
                    # Check if FVG matches expected
                    if (signal['fvg_zone_low'] <= float(period['expected_fvg'].split('-')[0]) + 100 and
                        signal['fvg_zone_high'] >= float(period['expected_fvg'].split('-')[1]) - 100):
                        print(f"      ✅ FVG matches expected zone!")
                    else:
                        print(f"      ⚠️ FVG doesn't match expected zone")
            else:
                print(f"   ❌ No signals generated")
                
                # Debug: Check what's happening
                print(f"   🔍 Debug Info:")
                
                # Check active FVGs at start of period
                start_dt = pd.to_datetime(period['start'])
                active_fvgs = []
                
                for fvg in htf_pools.get('fvg_pools', []):
                    fvg_time = pd.to_datetime(fvg['timestamp'])
                    if fvg_time < start_dt:
                        # Check if not mitigated
                        if fvg.get('mitigation_time') is None:
                            active_fvgs.append(fvg)
                        else:
                            mitigation_time = pd.to_datetime(fvg['mitigation_time'])
                            if mitigation_time > start_dt:
                                active_fvgs.append(fvg)
                
                print(f"      • Active FVGs at start: {len(active_fvgs)}")
                for fvg in active_fvgs[:3]:  # Show first 3
                    print(f"         - {fvg['timestamp']}: {fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}")
                
                # Check candles
                print(f"      • LTF Candles: {len(candles_ltf)}")
                
                if candles_ltf:
                    first_candle = candles_ltf[0]
                    last_candle = candles_ltf[-1]
                    print(f"      • First candle: {first_candle['timestamp']} - {first_candle['close']:.2f}")
                    print(f"      • Last candle: {last_candle['timestamp']} - {last_candle['close']:.2f}")
                    
                    # Check if price touched expected FVG zone
                    expected_low = float(period['expected_fvg'].split('-')[0])
                    expected_high = float(period['expected_fvg'].split('-')[1])
                    
                    touches = 0
                    for candle in candles_ltf:
                        if candle['low'] <= expected_high and candle['high'] >= expected_low:
                            touches += 1
                    
                    print(f"      • Candles touching expected FVG zone: {touches}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n✅ Analysis Complete!")
    db.close()


if __name__ == "__main__":
    check_strategy_during_touches()
