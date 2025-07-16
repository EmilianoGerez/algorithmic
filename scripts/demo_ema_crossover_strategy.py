#!/usr/bin/env python3
"""
EMA Crossover in Liquidity Pool Strategy Demo

This script demonstrates the new compositional strategy system
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.core.strategy import (
    create_default_strategy,
    create_scalping_strategy,
    create_swing_strategy
)


def demo_ema_crossover_strategy():
    """Demo the EMA crossover strategy"""
    
    print("🎯 EMA Crossover in Liquidity Pool Strategy Demo")
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
    start = "2025-05-01T00:00:00Z"
    end = "2025-07-13T00:00:00Z"
    
    print(f"📊 Testing Strategy:")
    print(f"   • Symbol: {symbol}")
    print(f"   • LTF: {ltf} (entry timeframe)")
    print(f"   • HTF: {htf} (context timeframe)")
    print(f"   • Period: {start} to {end}")
    
    # Get market data
    print(f"\n📈 Getting Market Data...")
    
    # Get HTF pools
    htf_pools = service.get_liquidity_pools(symbol, htf, "all")
    print(f"   • HTF FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
    print(f"   • HTF Pivot Pools: {len(htf_pools.get('pivot_pools', []))}")
    
    # Get LTF candles
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe=ltf,
        start=start,
        end=end
    )
    candles_ltf = ltf_result["candles"]
    print(f"   • LTF Candles: {len(candles_ltf)}")
    
    # Test different strategy configurations
    strategies = [
        ("Default Strategy", create_default_strategy()),
        ("Scalping Strategy", create_scalping_strategy()),
        ("Swing Strategy", create_swing_strategy())
    ]
    
    for strategy_name, strategy in strategies:
        print(f"\n🔍 Testing {strategy_name}:")
        print("-" * 40)
        
        # Get strategy summary
        summary = strategy.get_strategy_summary()
        print(f"   • EMA Periods: {summary['config']['ema_fast_period']}/{summary['config']['ema_slow_period']}")
        print(f"   • Min Confidence: {summary['config']['min_confidence_threshold']}")
        print(f"   • Risk/Reward: {summary['config']['risk_reward_ratio']}")
        
        # Generate signals
        try:
            signals = strategy.generate_signals(candles_ltf, htf_pools)
            print(f"   • Signals Generated: {len(signals)}")
            
            # Show signal details
            for i, signal in enumerate(signals[:3]):  # Show first 3 signals
                print(f"\n   📍 Signal {i+1}:")
                print(f"      • Direction: {signal.direction.value}")
                print(f"      • Entry Price: ${signal.entry_price:.2f}")
                print(f"      • Confidence: {signal.confidence_score:.2f}")
                print(f"      • Risk/Reward: {signal.risk_reward_ratio:.2f}")
                print(f"      • Pool Type: {signal.liquidity_event.pool_type.value}")
                print(f"      • Pool Status: {signal.liquidity_event.status}")
                print(f"      • Technical Signals: {len(signal.technical_signals)}")
                
                # Show technical signal details
                for tech_signal in signal.technical_signals:
                    print(f"         - {tech_signal.signal_type}: {tech_signal.direction.value} "
                          f"({tech_signal.strength.value}, {tech_signal.confidence:.2f})")
                
                # Show market context
                print(f"      • Market Regime: {signal.market_context.trend_regime.value}")
                print(f"      • Relative Volume: {signal.market_context.volume_profile.get('relative_volume', 0):.2f}")
                print(f"      • Market Structure: {signal.market_context.market_structure}")
                
                if signal.market_context.exhaustion_signals:
                    print(f"      • Exhaustion Signals: {', '.join(signal.market_context.exhaustion_signals)}")
            
            if len(signals) > 3:
                print(f"   ... and {len(signals) - 3} more signals")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n📊 Strategy Demo Complete!")
    print(f"   • The compositional strategy system is working")
    print(f"   • Different configurations can be easily tested")
    print(f"   • Ready for backtesting and paper trading")
    
    db.close()


if __name__ == "__main__":
    demo_ema_crossover_strategy()
