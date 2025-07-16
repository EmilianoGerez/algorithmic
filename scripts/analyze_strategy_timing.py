#!/usr/bin/env python3
"""
Deep Analysis of EMA Crossover Strategy Components
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from datetime import datetime, timedelta
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.core.strategy.detectors.liquidity_pool_detectors import FVGPoolDetector, PivotPoolDetector
from src.core.strategy.indicators.technical_indicators import EMACrossoverIndicator
from src.core.strategy.evaluators.market_context_evaluators import BasicMarketContextEvaluator


def analyze_strategy_timing():
    """Analyze timing of pool interactions vs EMA crossovers"""
    
    print("🔍 Deep Analysis: EMA Crossover Strategy Components")
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
    
    print(f"📊 Analysis Period: {start} to {end}")
    
    # Get data
    print(f"\n📈 Loading Data...")
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
    
    # 1. Analyze EMA Crossovers
    print(f"\n1️⃣ EMA Crossover Analysis:")
    print("-" * 40)
    
    df = pd.DataFrame(candles_ltf)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['ema_fast'] = df['close'].ewm(span=9).mean()
    df['ema_slow'] = df['close'].ewm(span=20).mean()
    
    # Detect crossovers
    df['ema_fast_above'] = df['ema_fast'] > df['ema_slow']
    df['ema_cross'] = df['ema_fast_above'] != df['ema_fast_above'].shift(1)
    
    crossovers = df[df['ema_cross']].copy()
    crossovers['direction'] = crossovers['ema_fast_above'].apply(
        lambda x: 'Bullish' if x else 'Bearish'
    )
    
    print(f"   • Total EMA Crossovers: {len(crossovers)}")
    print(f"   • Bullish Crossovers: {len(crossovers[crossovers['direction'] == 'Bullish'])}")
    print(f"   • Bearish Crossovers: {len(crossovers[crossovers['direction'] == 'Bearish'])}")
    
    # Show some crossover examples
    if len(crossovers) > 0:
        print(f"\n   📅 Recent Crossover Examples:")
        for idx, row in crossovers.tail(5).iterrows():
            print(f"      • {row['timestamp']}: {row['direction']} - Price: ${row['close']:.2f}")
    
    # 2. Analyze Pool Interactions
    print(f"\n2️⃣ Pool Interaction Analysis:")
    print("-" * 40)
    
    # Use limited pools for faster processing
    limited_fvg_pools = htf_pools.get('fvg_pools', [])[:5]
    limited_pivot_pools = htf_pools.get('pivot_pools', [])[:5]
    
    # Test FVG interactions
    fvg_detector = FVGPoolDetector()
    fvg_events = fvg_detector.detect_events(candles_ltf, limited_fvg_pools)
    
    print(f"   • FVG Pool Events: {len(fvg_events)}")
    
    # Test Pivot interactions
    pivot_detector = PivotPoolDetector()
    pivot_events = pivot_detector.detect_events(candles_ltf, limited_pivot_pools)
    
    print(f"   • Pivot Pool Events: {len(pivot_events)}")
    
    # Show some pool interaction examples
    all_pool_events = fvg_events + pivot_events
    all_pool_events.sort(key=lambda x: x.timestamp)
    
    if all_pool_events:
        print(f"\n   📅 Recent Pool Interaction Examples:")
        for event in all_pool_events[-5:]:
            print(f"      • {event.timestamp}: {event.pool_type.value} {event.status} - Price: ${event.price:.2f}")
    
    # 3. Timing Analysis
    print(f"\n3️⃣ Timing Overlap Analysis:")
    print("-" * 40)
    
    # Convert to DataFrame for easier analysis
    crossover_times = set(crossovers['timestamp'].dt.floor('15T'))  # Round to 15-minute intervals
    pool_event_times = set(pd.to_datetime([event.timestamp for event in all_pool_events]).floor('15T'))
    
    print(f"   • Crossover Time Slots: {len(crossover_times)}")
    print(f"   • Pool Event Time Slots: {len(pool_event_times)}")
    
    # Find overlaps
    overlaps = crossover_times.intersection(pool_event_times)
    print(f"   • Overlapping Time Slots: {len(overlaps)}")
    
    if overlaps:
        print(f"\n   🎯 Overlapping Events:")
        for overlap_time in sorted(overlaps):
            # Find crossovers at this time
            crossover_at_time = crossovers[crossovers['timestamp'].dt.floor('15T') == overlap_time]
            # Find pool events at this time
            pool_events_at_time = [
                event for event in all_pool_events 
                if pd.to_datetime(event.timestamp).floor('15T') == overlap_time
            ]
            
            for _, cross in crossover_at_time.iterrows():
                for event in pool_events_at_time:
                    print(f"      • {overlap_time}: {cross['direction']} crossover + {event.pool_type.value} {event.status}")
    
    # 4. Test EMA Indicator at Pool Events
    print(f"\n4️⃣ EMA Indicator Response to Pool Events:")
    print("-" * 40)
    
    ema_indicator = EMACrossoverIndicator()
    context_evaluator = BasicMarketContextEvaluator()
    
    successful_signals = 0
    
    # Test EMA indicator at each pool event
    for event in all_pool_events[:10]:  # Test first 10 events
        try:
            # Get context
            context = context_evaluator.evaluate_context(candles_ltf, event)
            
            # Test EMA signal
            ema_signal = ema_indicator.generate_signal(candles_ltf, context)
            
            if ema_signal:
                successful_signals += 1
                print(f"   ✅ Signal at {event.timestamp}: {ema_signal.direction.value} crossover")
                print(f"      • Pool: {event.pool_type.value} {event.status}")
                print(f"      • EMA Confidence: {ema_signal.confidence:.2f}")
                print(f"      • EMA Fast: {ema_signal.values['ema_fast']:.2f}")
                print(f"      • EMA Slow: {ema_signal.values['ema_slow']:.2f}")
                print()
        except Exception as e:
            print(f"   ❌ Error testing event {event.timestamp}: {e}")
    
    print(f"   • Successful EMA Signals: {successful_signals} out of {min(10, len(all_pool_events))} tested")
    
    # 5. Summary and Recommendations
    print(f"\n5️⃣ Summary & Recommendations:")
    print("-" * 40)
    
    crossover_rate = len(crossovers) / len(candles_ltf) * 100
    pool_event_rate = len(all_pool_events) / len(candles_ltf) * 100
    
    print(f"   • EMA Crossover Rate: {crossover_rate:.2f}% of candles")
    print(f"   • Pool Event Rate: {pool_event_rate:.2f}% of candles")
    print(f"   • Timing Overlap: {len(overlaps)} instances")
    
    if len(overlaps) == 0:
        print(f"\n   💡 Recommendations:")
        print(f"      • Consider widening the time window for EMA crossover detection")
        print(f"      • Try shorter EMA periods (5/13 instead of 9/20)")
        print(f"      • Lower confidence threshold to capture more signals")
        print(f"      • Allow EMA crossovers within N candles of pool events")
    
    print(f"\n✅ Analysis Complete!")
    
    db.close()


if __name__ == "__main__":
    analyze_strategy_timing()
