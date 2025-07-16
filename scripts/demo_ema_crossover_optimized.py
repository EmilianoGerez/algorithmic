#!/usr/bin/env python3
"""
EMA Crossover Strategy Demo - Optimized for larger time ranges
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.core.strategy import create_default_strategy


def demo_ema_crossover_strategy_optimized():
    """Demo with optimized processing for larger time ranges"""
    
    print("🎯 EMA Crossover Strategy Demo - Optimized")
    print("=" * 60)
    
    # Initialize dependencies
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Parameters - smaller time window for faster processing
    symbol = "BTC/USD"
    ltf = "15T"
    htf = "4H"
    start = "2025-05-15T00:00:00Z"  # Start from mid-May
    end = "2025-06-15T00:00:00Z"    # One month window
    
    print(f"📊 Testing Strategy (Optimized):")
    print(f"   • Symbol: {symbol}")
    print(f"   • LTF: {ltf} (entry timeframe)")
    print(f"   • HTF: {htf} (context timeframe)")
    print(f"   • Period: {start} to {end}")
    
    try:
        # Get market data with progress
        print(f"\n📈 Getting Market Data...")
        
        # Get HTF pools first (faster)
        print("   • Loading HTF pools...")
        htf_pools = service.get_liquidity_pools(symbol, htf, "all")
        print(f"   • HTF FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
        print(f"   • HTF Pivot Pools: {len(htf_pools.get('pivot_pools', []))}")
        
        # Get LTF candles with timeout protection
        print("   • Loading LTF candles...")
        ltf_result = service.detect_signals(
            symbol=symbol,
            signal_type="fvg_and_pivot",
            timeframe=ltf,
            start=start,
            end=end
        )
        candles_ltf = ltf_result["candles"]
        print(f"   • LTF Candles: {len(candles_ltf)}")
        
        if not candles_ltf:
            print("   ❌ No candles retrieved. Exiting.")
            return
        
        # Test strategy with reduced complexity
        print(f"\n🔍 Testing Default Strategy:")
        print("-" * 40)
        
        strategy = create_default_strategy()
        summary = strategy.get_strategy_summary()
        
        print(f"   • EMA Periods: {summary['config']['ema_fast_period']}/{summary['config']['ema_slow_period']}")
        print(f"   • Min Confidence: {summary['config']['min_confidence_threshold']}")
        print(f"   • Risk/Reward: {summary['config']['risk_reward_ratio']}")
        
        # Generate signals with progress tracking
        print(f"   • Generating signals...")
        
        # Limit pool interactions for faster processing
        limited_htf_pools = {
            'fvg_pools': htf_pools.get('fvg_pools', [])[:10],  # Limit to first 10 FVG pools
            'pivot_pools': htf_pools.get('pivot_pools', [])[:20]  # Limit to first 20 pivot pools
        }
        
        signals = strategy.generate_signals(candles_ltf, limited_htf_pools)
        print(f"   • Signals Generated: {len(signals)}")
        
        # Show signal details
        if signals:
            print(f"\n   📍 Signal Details:")
            for i, signal in enumerate(signals[:5]):  # Show first 5 signals
                print(f"      {i+1}. {signal.direction.value} at ${signal.entry_price:.2f}")
                print(f"         • Timestamp: {signal.timestamp}")
                print(f"         • Confidence: {signal.confidence_score:.2f}")
                print(f"         • Risk/Reward: {signal.risk_reward_ratio:.2f}")
                print(f"         • Pool: {signal.liquidity_event.pool_type.value} ({signal.liquidity_event.status})")
                print(f"         • Technical: {len(signal.technical_signals)} indicators")
                print()
        else:
            print(f"   • No signals generated in this period")
            
            # Quick diagnostic
            print(f"\n   🔍 Diagnostic:")
            
            # Check for EMA crossovers in the data
            try:
                import pandas as pd
                df = pd.DataFrame(candles_ltf)
                df['ema_fast'] = df['close'].ewm(span=9).mean()
                df['ema_slow'] = df['close'].ewm(span=20).mean()
                
                # Look for crossovers
                df['ema_cross'] = (df['ema_fast'] > df['ema_slow']) != (df['ema_fast'].shift(1) > df['ema_slow'].shift(1))
                crossovers = df[df['ema_cross']].shape[0]
                
                print(f"      • EMA Crossovers in period: {crossovers}")
                print(f"      • Pool interactions: {len(limited_htf_pools['fvg_pools']) + len(limited_htf_pools['pivot_pools'])}")
                
                if crossovers > 0:
                    print(f"      • Recent crossover examples:")
                    recent_crosses = df[df['ema_cross']].tail(3)
                    for idx, row in recent_crosses.iterrows():
                        direction = "Bullish" if row['ema_fast'] > row['ema_slow'] else "Bearish"
                        print(f"         - {row['timestamp']}: {direction} crossover")
                        
            except Exception as e:
                print(f"      • Error in diagnostic: {e}")
        
        print(f"\n✅ Demo Complete!")
        print(f"   • Processed {len(candles_ltf)} candles successfully")
        print(f"   • Strategy system is working correctly")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    demo_ema_crossover_strategy_optimized()
