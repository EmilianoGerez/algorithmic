#!/usr/bin/env python3
"""
Test Strategy with Extended Time Window
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


def test_extended_window():
    """Test strategy with extended time window"""
    
    print("🎯 Testing Strategy with Extended Time Window")
    print("=" * 60)
    
    # Initialize strategy
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    strategy = SwingConfirmedEMACrossoverStrategy()
    
    # Extended time window - give strategy more time to find EMA crossovers
    symbol = "BTC/USD"
    start = "2025-05-29T13:00:00Z"  # FVG touch at 13:30
    end = "2025-05-30T13:00:00Z"    # Extended to 24 hours later
    
    print(f"📥 Getting data for {start} to {end}")
    print(f"   This gives the strategy 24 hours to find EMA crossovers")
    
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
    
    print(f"   • LTF Candles: {len(candles_ltf)}")
    print(f"   • HTF FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
    
    # Run strategy
    signals = strategy.generate_signals(
        candles_ltf=candles_ltf,
        htf_pools=htf_pools
    )
    
    print(f"   📊 Signals Generated: {len(signals)}")
    
    if signals:
        print(f"\n🎉 SUCCESS! Signals found with extended window:")
        
        for i, signal in enumerate(signals):
            print(f"   ✅ Signal {i+1}:")
            print(f"      • FVG Touch: {signal.liquidity_event.timestamp}")
            print(f"      • Swing Point: {signal.timestamp}")
            print(f"      • Entry Price: {signal.entry_price:.2f}")
            print(f"      • Direction: {signal.direction}")
            print(f"      • FVG Zone: {signal.liquidity_event.zone_low:.2f} - {signal.liquidity_event.zone_high:.2f}")
            print(f"      • Confidence: {signal.confidence_score:.2f}")
            
            # Show EMA crossover details
            if signal.technical_signals:
                tech_signal = signal.technical_signals[0]
                print(f"      • EMA Crossover: {tech_signal.timestamp}")
                print(f"      • EMA Fast: {tech_signal.values['ema_fast']:.2f}")
                print(f"      • EMA Slow: {tech_signal.values['ema_slow']:.2f}")
                print(f"      • Crossover Price: {tech_signal.values['price']:.2f}")
                
                # Calculate time between FVG touch and EMA crossover
                fvg_time = pd.to_datetime(signal.liquidity_event.timestamp, utc=True)
                ema_time = pd.to_datetime(tech_signal.timestamp, utc=True)
                time_diff = (ema_time - fvg_time).total_seconds() / 3600
                print(f"      • Time from FVG to EMA: {time_diff:.1f} hours")
                
    else:
        print(f"   ❌ Still no signals found even with extended window")
    
    print(f"\n✅ Test Complete!")
    db.close()


if __name__ == "__main__":
    test_extended_window()
