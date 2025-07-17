#!/usr/bin/env python3
"""
Test Time-Aware FVG Strategy - Fixes Data Leakage Issues
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.core.strategy.time_aware_fvg_strategy import create_time_aware_strategy


def test_time_aware_strategy():
    """Test the time-aware strategy that fixes data leakage"""
    
    print("🔧 Testing Time-Aware FVG Strategy (Fixes Data Leakage)")
    print("=" * 80)
    print("Key Improvements:")
    print("1. Only uses FVGs that were 'created' before evaluation time")
    print("2. Respects FVG mitigation status at evaluation time")
    print("3. Processes candles chronologically (simulates real-time)")
    print("4. No future data leakage")
    print("=" * 80)
    
    # Initialize dependencies
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Parameters - focusing on periods you mentioned
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    start = "2025-05-25T00:00:00Z"  # Extended to catch May 27 signal
    end = "2025-06-05T00:00:00Z"    # Extended to catch Jun 1 and Jun 3 signals
    
    print(f"📊 Testing Period: {start} to {end}")
    print(f"📈 Symbol: {symbol}")
    print(f"⏰ LTF: {ltf}, HTF: {htf}")
    print(f"🎯 Looking for signals around:")
    print(f"   • May 27 around 3:00 AM")
    print(f"   • Jun 1 around 9:30 AM")
    print(f"   • Jun 3 around 9:30 AM")
    
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
    
    # Show some FVG pool info
    fvg_pools = htf_pools.get('fvg_pools', [])
    print(f"\n📋 FVG Pool Sample (first 10):")
    for i, fvg in enumerate(fvg_pools[:10]):
        print(f"   {i+1}. {fvg['timestamp']} - {fvg.get('direction', 'unknown')} - Status: {fvg.get('status', 'unknown')}")
    
    # Test time-aware strategy
    config = {
        "ema_fast_period": 9,
        "ema_slow_period": 20,
        "swing_lookback_candles": 3,
        "confirmation_window_hours": 12,
        "min_confidence_threshold": 0.6,
        "fvg_lookback_hours": 72  # 3 days lookback
    }
    
    strategy = create_time_aware_strategy(config)
    
    print(f"\n🔧 Strategy Configuration:")
    print(f"   • EMA Periods: {config['ema_fast_period']}/{config['ema_slow_period']}")
    print(f"   • Swing Lookback: {config['swing_lookback_candles']} candles")
    print(f"   • Confirmation Window: {config['confirmation_window_hours']} hours")
    print(f"   • FVG Lookback: {config['fvg_lookback_hours']} hours")
    print(f"   • Min Confidence: {config['min_confidence_threshold']}")
    
    # Generate signals
    print(f"\n🎯 Generating Signals with Time-Aware Processing...")
    try:
        signals = strategy.generate_signals(candles_ltf, htf_pools)
        
        if signals:
            print(f"\n🎉 Generated {len(signals)} signals!")
            
            # Analyze signals by date
            signals_by_date = {}
            for signal in signals:
                date_str = str(signal.timestamp).split(' ')[0]
                if date_str not in signals_by_date:
                    signals_by_date[date_str] = []
                signals_by_date[date_str].append(signal)
            
            print(f"\n📅 Signals by Date:")
            for date, date_signals in sorted(signals_by_date.items()):
                print(f"   {date}: {len(date_signals)} signals")
                for i, signal in enumerate(date_signals):
                    time_str = str(signal.timestamp).split(' ')[1]
                    print(f"      {i+1}. {time_str} - {signal.direction.value} - Conf: {signal.confidence_score:.2f}")
            
            # Show detailed analysis for each signal
            print(f"\n🔍 Detailed Signal Analysis:")
            for i, signal in enumerate(signals):
                print(f"\n--- SIGNAL #{i+1} ---")
                print(f"Signal Time: {signal.timestamp}")
                print(f"Direction: {signal.direction.value}")
                print(f"Confidence: {signal.confidence_score:.3f}")
                print(f"Entry Price: ${signal.entry_price:.2f}")
                print(f"FVG Touch: {signal.liquidity_event.timestamp}")
                print(f"FVG Price: ${signal.liquidity_event.price:.2f}")
                
                if signal.technical_signals:
                    tech_signal = signal.technical_signals[0]
                    print(f"EMA Crossover: {tech_signal.timestamp}")
                    print(f"EMA 9: {tech_signal.values['ema_fast']:.2f}")
                    print(f"EMA 20: {tech_signal.values['ema_slow']:.2f}")
        else:
            print(f"\n❌ No signals generated")
            print(f"Possible reasons:")
            print(f"   • FVGs already mitigated in evaluation window")
            print(f"   • No valid swing points formed")
            print(f"   • No EMA crossovers in confirmation window")
            print(f"   • Confidence below threshold")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n✅ Testing Complete!")
    db.close()


if __name__ == "__main__":
    test_time_aware_strategy()
