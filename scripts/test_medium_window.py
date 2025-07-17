#!/usr/bin/env python3
"""
Test Strategy with Medium Time Window
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


def test_medium_window():
    """Test strategy with medium time window"""
    
    print("🎯 Testing Strategy with Medium Time Window")
    print("=" * 60)
    
    # Initialize strategy
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    strategy = SwingConfirmedEMACrossoverStrategy()
    
    # Test different window sizes
    test_windows = [
        {
            "name": "6 Hours",
            "start": "2025-05-29T13:00:00Z",
            "end": "2025-05-29T19:00:00Z"
        },
        {
            "name": "12 Hours", 
            "start": "2025-05-29T13:00:00Z",
            "end": "2025-05-30T01:00:00Z"
        },
        {
            "name": "Original June 5 Window",
            "start": "2025-06-05T00:00:00Z",
            "end": "2025-06-06T00:00:00Z"
        }
    ]
    
    for window in test_windows:
        print(f"\n🔍 Testing: {window['name']}")
        print(f"   Period: {window['start']} to {window['end']}")
        
        try:
            # Get data
            ltf_result = service.detect_signals(
                symbol="BTC/USD",
                signal_type="fvg_and_pivot",
                timeframe="15T",
                start=window['start'],
                end=window['end']
            )
            candles_ltf = ltf_result["candles"]
            
            htf_pools = service.get_liquidity_pools("BTC/USD", "4H", "all")
            
            print(f"   • LTF Candles: {len(candles_ltf)}")
            
            # Run strategy
            signals = strategy.generate_signals(
                candles_ltf=candles_ltf,
                htf_pools=htf_pools
            )
            
            print(f"   📊 Signals Generated: {len(signals)}")
            
            if signals:
                for i, signal in enumerate(signals[:2]):  # Show first 2
                    print(f"      ✅ Signal {i+1}: {signal.timestamp} at {signal.entry_price:.2f}")
                    
                    # Show timing
                    fvg_time = pd.to_datetime(signal.liquidity_event.timestamp, utc=True)
                    swing_time = pd.to_datetime(signal.timestamp, utc=True)
                    
                    if signal.technical_signals:
                        ema_time = pd.to_datetime(signal.technical_signals[0].timestamp, utc=True)
                        
                        fvg_to_swing = (swing_time - fvg_time).total_seconds() / 3600
                        swing_to_ema = (ema_time - swing_time).total_seconds() / 3600
                        
                        print(f"         FVG → Swing: {fvg_to_swing:.1f}h")
                        print(f"         Swing → EMA: {swing_to_ema:.1f}h")
                        print(f"         Total: {fvg_to_swing + swing_to_ema:.1f}h")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n✅ Test Complete!")
    db.close()


if __name__ == "__main__":
    test_medium_window()
