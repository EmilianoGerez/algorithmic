#!/usr/bin/env python3
"""
Simplified Test of Time-Aware Strategy
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
import pandas as pd
from src.core.strategy.time_aware_fvg_strategy import TimeAwareFVGStrategy
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


def simple_test():
    """Simple test of time-aware strategy"""
    
    print("🔍 Simple Test of Time-Aware Strategy")
    print("=" * 50)
    
    # Initialize 
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    strategy = TimeAwareFVGStrategy()
    
    # Get data for a specific period with known FVG touches
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    start = "2025-05-29T13:00:00Z"
    end = "2025-05-29T14:00:00Z"  # Short period
    
    print(f"📥 Getting data for {start} to {end}")
    
    # Get LTF data
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe=ltf,
        start=start,
        end=end
    )
    candles_ltf = ltf_result["candles"]
    
    # Get HTF data
    htf_pools = service.get_liquidity_pools(symbol, htf, "all")
    
    print(f"   • LTF Candles: {len(candles_ltf)}")
    print(f"   • HTF FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
    
    # Test the active FVGs method first
    print(f"\n🔍 Testing active FVGs at specific time:")
    
    test_time = pd.to_datetime("2025-05-29T13:30:00Z", utc=True)
    active_fvgs = strategy._get_active_fvgs_at_time(htf_pools, test_time)
    
    print(f"   • Active FVGs at {test_time}: {len(active_fvgs)}")
    
    for i, fvg in enumerate(active_fvgs[:5]):
        print(f"      {i+1}. {fvg['timestamp']}: {fvg['zone_low']:.2f}-{fvg['zone_high']:.2f} ({fvg['direction']})")
        
        # Check if candle price is near this FVG
        if candles_ltf:
            candle_price = candles_ltf[0]['close']
            distance = min(
                abs(candle_price - fvg['zone_low']),
                abs(candle_price - fvg['zone_high'])
            )
            print(f"         Distance to price {candle_price:.2f}: {distance:.2f}")
    
    # Test with a minimal candle set
    print(f"\n🔍 Testing with first 5 candles:")
    
    try:
        minimal_candles = candles_ltf[:5]
        print(f"   • Using {len(minimal_candles)} candles")
        
        # Show candle timestamps
        for i, candle in enumerate(minimal_candles):
            print(f"      {i+1}. {candle['timestamp']}: {candle['close']:.2f}")
        
        # Try to generate signals
        signals = strategy.generate_signals(
            candles_ltf=minimal_candles,
            htf_pools=htf_pools
        )
        
        print(f"   • Generated {len(signals)} signals")
        
        for signal in signals:
            print(f"      ✅ Signal: {signal.timestamp} at {signal.price:.2f}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n✅ Test Complete!")
    db.close()


if __name__ == "__main__":
    simple_test()
