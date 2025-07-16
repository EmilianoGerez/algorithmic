#!/usr/bin/env python3
"""
Test Time Window EMA Crossover Strategy
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.core.strategy.time_window_ema_strategy import create_time_window_strategy


def test_time_window_strategy():
    """Test the time window strategy"""
    
    print("🚀 Testing Time Window EMA Crossover Strategy")
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
    start = "2025-05-15T00:00:00Z"
    end = "2025-06-15T00:00:00Z"
    
    print(f"📊 Testing Period: {start} to {end}")
    print(f"📈 Symbol: {symbol}")
    print(f"⏰ LTF: {ltf}, HTF: {htf}")
    
    # Get data
    print(f"\n📥 Loading Data...")
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
    print(f"   • HTF Pivot Pools: {len(htf_pools.get('pivot_pools', []))}")
    
    # Test different configurations
    configs = [
        {
            "name": "Default (9/20 EMA, 2h window)",
            "config": {
                "ema_fast_period": 9,
                "ema_slow_period": 20,
                "time_window_hours": 2,
                "min_confidence_threshold": 0.6
            }
        },
        {
            "name": "Aggressive (5/13 EMA, 4h window)",
            "config": {
                "ema_fast_period": 5,
                "ema_slow_period": 13,
                "time_window_hours": 4,
                "min_confidence_threshold": 0.5
            }
        },
        {
            "name": "Conservative (21/50 EMA, 1h window)",
            "config": {
                "ema_fast_period": 21,
                "ema_slow_period": 50,
                "time_window_hours": 1,
                "min_confidence_threshold": 0.7
            }
        }
    ]
    
    # Test each configuration
    for test_config in configs:
        print(f"\n🔧 Testing: {test_config['name']}")
        print("-" * 50)
        
        strategy = create_time_window_strategy(test_config['config'])
        
        try:
            signals = strategy.generate_signals(candles_ltf, htf_pools)
            
            print(f"   ✅ Generated {len(signals)} signals")
            
            if signals:
                # Analyze signals
                bullish_signals = [s for s in signals if s.direction.value == 'bullish']
                bearish_signals = [s for s in signals if s.direction.value == 'bearish']
                
                print(f"   📈 Bullish Signals: {len(bullish_signals)}")
                print(f"   📉 Bearish Signals: {len(bearish_signals)}")
                
                # Show confidence distribution
                confidences = [s.confidence_score for s in signals]
                avg_confidence = sum(confidences) / len(confidences)
                print(f"   🎯 Average Confidence: {avg_confidence:.2f}")
                
                # Show sample signals
                print(f"   📋 Sample Signals:")
                for i, signal in enumerate(signals[:3]):
                    print(f"      {i+1}. {signal.timestamp}: {signal.direction.value} - "
                          f"Confidence: {signal.confidence_score:.2f} - "
                          f"Pool: {signal.liquidity_event.pool_type.value}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n✅ Testing Complete!")
    db.close()


if __name__ == "__main__":
    test_time_window_strategy()
