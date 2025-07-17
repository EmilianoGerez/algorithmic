#!/usr/bin/env python3
"""
Test Original Working Strategy During FVG Touches
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
import pandas as pd
from src.core.strategy.swing_confirmed_ema_strategy import SwingConfirmedEMACrossoverStrategy
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


def test_original_strategy():
    """Test original working strategy during FVG touches"""
    
    print("🎯 Testing Original Strategy During FVG Touches")
    print("=" * 60)
    
    # Initialize strategy
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    strategy = SwingConfirmedEMACrossoverStrategy()
    
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
        }
    ]
    
    for period in test_periods:
        print(f"\n🔍 Testing: {period['name']}")
        print(f"   Period: {period['start']} to {period['end']}")
        print(f"   Expected FVG: {period['expected_fvg']}")
        
        try:
            # Get data for this period
            ltf_result = service.detect_signals(
                symbol="BTC/USD",
                signal_type="fvg_and_pivot",
                timeframe="15T",
                start=period['start'],
                end=period['end']
            )
            candles_ltf = ltf_result["candles"]
            
            htf_pools = service.get_liquidity_pools("BTC/USD", "4H", "all")
            
            print(f"   📊 Data: {len(candles_ltf)} candles, {len(htf_pools.get('fvg_pools', []))} FVGs")
            
            # Run strategy
            signals = strategy.generate_signals(
                candles_ltf=candles_ltf,
                htf_pools=htf_pools
            )
            
            print(f"   📊 Signals Generated: {len(signals)}")
            
            if signals:
                for i, signal in enumerate(signals):
                    print(f"   ✅ Signal {i+1}:")
                    print(f"      • Time: {signal.timestamp}")
                    print(f"      • Price: {signal.entry_price:.2f}")
                    print(f"      • Direction: {signal.direction}")
                    print(f"      • FVG Zone: {signal.liquidity_event.zone_low:.2f} - {signal.liquidity_event.zone_high:.2f}")
                    print(f"      • Confidence: {signal.confidence_score:.2f}")
                    
                    # Check if FVG matches expected
                    expected_low = float(period['expected_fvg'].split('-')[0])
                    expected_high = float(period['expected_fvg'].split('-')[1])
                    
                    if (signal.liquidity_event.zone_low <= expected_low + 100 and
                        signal.liquidity_event.zone_high >= expected_high - 100):
                        print(f"      ✅ FVG matches expected zone!")
                    else:
                        print(f"      ⚠️ FVG doesn't match expected zone")
            else:
                print(f"   ❌ No signals generated")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ Analysis Complete!")
    db.close()


if __name__ == "__main__":
    test_original_strategy()
