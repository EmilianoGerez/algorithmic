#!/usr/bin/env python3
"""
Debug script for EMA Crossover Strategy
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.core.strategy.detectors.liquidity_pool_detectors import FVGPoolDetector, PivotPoolDetector
from src.core.strategy.indicators.technical_indicators import EMACrossoverIndicator
from src.core.strategy.evaluators.market_context_evaluators import BasicMarketContextEvaluator


def debug_strategy_components():
    """Debug individual strategy components"""
    
    print("🔍 Debug EMA Crossover Strategy Components")
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
    start = "2025-07-01T00:00:00Z"
    end = "2025-07-13T00:00:00Z"
    
    # Get market data
    print(f"📈 Getting Market Data...")
    htf_pools = service.get_liquidity_pools(symbol, htf, "all")
    
    ltf_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe=ltf,
        start=start,
        end=end
    )
    candles_ltf = ltf_result["candles"]
    
    print(f"   • HTF FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
    print(f"   • HTF Pivot Pools: {len(htf_pools.get('pivot_pools', []))}")
    print(f"   • LTF Candles: {len(candles_ltf)}")
    
    # Debug 1: Check pool data format
    print(f"\n1️⃣ Checking Pool Data Format:")
    print("-" * 40)
    
    fvg_pools = htf_pools.get('fvg_pools', [])
    if fvg_pools:
        print(f"   • Sample FVG Pool:")
        sample_fvg = fvg_pools[0]
        for key, value in sample_fvg.items():
            print(f"      {key}: {value}")
    else:
        print("   • No FVG pools found")
    
    pivot_pools = htf_pools.get('pivot_pools', [])
    if pivot_pools:
        print(f"   • Sample Pivot Pool:")
        sample_pivot = pivot_pools[0]
        for key, value in sample_pivot.items():
            print(f"      {key}: {value}")
    else:
        print("   • No Pivot pools found")
    
    # Debug 2: Test FVG detector
    print(f"\n2️⃣ Testing FVG Pool Detector:")
    print("-" * 40)
    
    fvg_detector = FVGPoolDetector()
    all_pools = fvg_pools + pivot_pools
    
    try:
        fvg_events = fvg_detector.detect_events(candles_ltf, all_pools)
        print(f"   • FVG Events Detected: {len(fvg_events)}")
        
        for i, event in enumerate(fvg_events[:3]):
            print(f"   • Event {i+1}:")
            print(f"      - Time: {event.timestamp}")
            print(f"      - Pool Type: {event.pool_type}")
            print(f"      - Status: {event.status}")
            print(f"      - Price: ${event.price:.2f}")
            print(f"      - Zone: ${event.zone_low:.2f} - ${event.zone_high:.2f}")
    except Exception as e:
        print(f"   ❌ Error in FVG detector: {e}")
        import traceback
        traceback.print_exc()
    
    # Debug 3: Test Pivot detector
    print(f"\n3️⃣ Testing Pivot Pool Detector:")
    print("-" * 40)
    
    pivot_detector = PivotPoolDetector()
    
    try:
        pivot_events = pivot_detector.detect_events(candles_ltf, all_pools)
        print(f"   • Pivot Events Detected: {len(pivot_events)}")
        
        for i, event in enumerate(pivot_events[:3]):
            print(f"   • Event {i+1}:")
            print(f"      - Time: {event.timestamp}")
            print(f"      - Pool Type: {event.pool_type}")
            print(f"      - Status: {event.status}")
            print(f"      - Price: ${event.price:.2f}")
            print(f"      - Zone: ${event.zone_low:.2f} - ${event.zone_high:.2f}")
    except Exception as e:
        print(f"   ❌ Error in Pivot detector: {e}")
        import traceback
        traceback.print_exc()
    
    # Debug 4: Test EMA indicator
    print(f"\n4️⃣ Testing EMA Crossover Indicator:")
    print("-" * 40)
    
    ema_indicator = EMACrossoverIndicator()
    context_evaluator = BasicMarketContextEvaluator()
    
    try:
        # Create a dummy event for context
        if candles_ltf:
            from src.core.strategy.composable_strategy import LiquidityPoolEvent, LiquidityPoolType, TrendDirection
            
            dummy_event = LiquidityPoolEvent(
                pool_type=LiquidityPoolType.FVG,
                timestamp=datetime.now(),
                price=candles_ltf[-1]['close'],
                direction=TrendDirection.BULLISH,
                zone_low=candles_ltf[-1]['close'] - 100,
                zone_high=candles_ltf[-1]['close'] + 100,
                status="touched",
                pool_id="debug_pool",
                timeframe="15T"
            )
            
            # Evaluate context
            context = context_evaluator.evaluate_context(candles_ltf, dummy_event)
            print(f"   • Market Context Generated: ✅")
            print(f"      - Trend Regime: {context.trend_regime.value}")
            print(f"      - Market Structure: {context.market_structure}")
            print(f"      - Relative Volume: {context.volume_profile.get('relative_volume', 0):.2f}")
            
            # Test EMA signal
            ema_signal = ema_indicator.generate_signal(candles_ltf, context)
            if ema_signal:
                print(f"   • EMA Signal Generated: ✅")
                print(f"      - Direction: {ema_signal.direction.value}")
                print(f"      - Strength: {ema_signal.strength.value}")
                print(f"      - Confidence: {ema_signal.confidence:.2f}")
                print(f"      - EMA Fast: {ema_signal.values['ema_fast']:.2f}")
                print(f"      - EMA Slow: {ema_signal.values['ema_slow']:.2f}")
            else:
                print(f"   • EMA Signal Generated: ❌ (No crossover detected)")
                
                # Check current EMA values
                import pandas as pd
                df = pd.DataFrame(candles_ltf)
                df['ema_fast'] = df['close'].ewm(span=9).mean()
                df['ema_slow'] = df['close'].ewm(span=20).mean()
                
                latest = df.iloc[-1]
                print(f"      - Current EMA Fast: {latest['ema_fast']:.2f}")
                print(f"      - Current EMA Slow: {latest['ema_slow']:.2f}")
                print(f"      - EMA Diff: {latest['ema_fast'] - latest['ema_slow']:.2f}")
                print(f"      - EMA Fast > Slow: {latest['ema_fast'] > latest['ema_slow']}")
    
    except Exception as e:
        print(f"   ❌ Error in EMA indicator: {e}")
        import traceback
        traceback.print_exc()
    
    # Debug 5: Check candle data format
    print(f"\n5️⃣ Checking Candle Data Format:")
    print("-" * 40)
    
    if candles_ltf:
        print(f"   • Sample Candle:")
        sample_candle = candles_ltf[0]
        for key, value in sample_candle.items():
            print(f"      {key}: {value}")
        
        print(f"   • Price Range:")
        prices = [c['close'] for c in candles_ltf]
        print(f"      - Min: ${min(prices):.2f}")
        print(f"      - Max: ${max(prices):.2f}")
        print(f"      - First: ${prices[0]:.2f}")
        print(f"      - Last: ${prices[-1]:.2f}")
    
    print(f"\n✅ Debug Complete!")
    
    db.close()


if __name__ == "__main__":
    debug_strategy_components()
