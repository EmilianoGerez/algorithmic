#!/usr/bin/env python3
"""
Test Swing Confirmed EMA Crossover Strategy
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.core.strategy.swing_confirmed_ema_strategy import create_swing_confirmed_strategy


def test_swing_confirmed_strategy():
    """Test the corrected swing confirmed strategy"""
    
    print("🎯 Testing Swing Confirmed EMA Crossover Strategy")
    print("=" * 70)
    print("Strategy Flow:")
    print("1. Price touches HTF FVG")
    print("2. Wait for LTF swing point formation (2-3 candles)")
    print("3. Look for EMA crossover within 4H window")
    print("4. Generate signal when all conditions align")
    print("=" * 70)
    
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
            "name": "Default (9/20 EMA, 3 candles swing, 12h window)",
            "config": {
                "ema_fast_period": 9,
                "ema_slow_period": 20,
                "swing_lookback_candles": 3,
                "confirmation_window_hours": 12,
                "min_confidence_threshold": 0.6
            }
        },
        {
            "name": "Sensitive (5/13 EMA, 2 candles swing, 16h window)",
            "config": {
                "ema_fast_period": 5,
                "ema_slow_period": 13,
                "swing_lookback_candles": 2,
                "confirmation_window_hours": 16,
                "min_confidence_threshold": 0.5
            }
        },
        {
            "name": "Conservative (21/50 EMA, 4 candles swing, 8h window)",
            "config": {
                "ema_fast_period": 21,
                "ema_slow_period": 50,
                "swing_lookback_candles": 4,
                "confirmation_window_hours": 8,
                "min_confidence_threshold": 0.7
            }
        }
    ]
    
    # Test each configuration
    for test_config in configs:
        print(f"\n🔧 Testing: {test_config['name']}")
        print("-" * 60)
        
        strategy = create_swing_confirmed_strategy(test_config['config'])
        
        try:
            signals = strategy.generate_signals(candles_ltf, htf_pools)
            
            if signals:
                print(f"   🎉 Generated {len(signals)} signals!")
                
                # Analyze signals
                bullish_signals = [s for s in signals if s.direction.value == 'bullish']
                bearish_signals = [s for s in signals if s.direction.value == 'bearish']
                
                print(f"   📈 Bullish Signals: {len(bullish_signals)}")
                print(f"   📉 Bearish Signals: {len(bearish_signals)}")
                
                # Show confidence distribution
                confidences = [s.confidence_score for s in signals]
                avg_confidence = sum(confidences) / len(confidences)
                print(f"   🎯 Average Confidence: {avg_confidence:.2f}")
                
                # Show detailed signal analysis
                print(f"   📋 Signal Details:")
                for i, signal in enumerate(signals[:5]):  # Show first 5
                    print(f"      {i+1}. {signal.timestamp}")
                    print(f"         Direction: {signal.direction.value}")
                    print(f"         Confidence: {signal.confidence_score:.2f}")
                    print(f"         Entry Price: ${signal.entry_price:.2f}")
                    print(f"         FVG Touch: {signal.liquidity_event.timestamp}")
                    print(f"         FVG Type: {signal.liquidity_event.pool_type.value}")
                    print(f"         FVG Direction: {signal.liquidity_event.direction.value}")
                    print()
            else:
                print(f"   ❌ No signals generated")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ Testing Complete!")
    db.close()


if __name__ == "__main__":
    test_swing_confirmed_strategy()
