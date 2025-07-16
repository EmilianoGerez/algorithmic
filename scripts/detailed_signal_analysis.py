#!/usr/bin/env python3
"""
Detailed Signal Analysis with Chart Verification Data
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


def get_detailed_signal_analysis():
    """Get detailed signal analysis for chart verification"""
    
    print("📊 Detailed Signal Analysis for Chart Verification")
    print("=" * 80)
    
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
    
    print(f"📈 Symbol: {symbol}")
    print(f"⏰ LTF: {ltf}, HTF: {htf}")
    print(f"📅 Period: {start} to {end}")
    
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
    
    # Test with default configuration
    config = {
        "ema_fast_period": 9,
        "ema_slow_period": 20,
        "swing_lookback_candles": 3,
        "confirmation_window_hours": 12,
        "min_confidence_threshold": 0.6
    }
    
    strategy = create_swing_confirmed_strategy(config)
    
    print(f"\n🔧 Strategy Configuration:")
    print(f"   • EMA Periods: {config['ema_fast_period']}/{config['ema_slow_period']}")
    print(f"   • Swing Lookback: {config['swing_lookback_candles']} candles")
    print(f"   • Confirmation Window: {config['confirmation_window_hours']} hours")
    print(f"   • Min Confidence: {config['min_confidence_threshold']}")
    
    # Generate signals
    print(f"\n🎯 Generating Signals...")
    signals = strategy.generate_signals(candles_ltf, htf_pools)
    
    if not signals:
        print("❌ No signals generated")
        return
    
    print(f"✅ Generated {len(signals)} signals\n")
    
    # Show detailed analysis for each signal
    for i, signal in enumerate(signals):
        print(f"🔍 SIGNAL #{i+1}")
        print("=" * 60)
        
        # Basic signal info
        print(f"📋 Signal Overview:")
        print(f"   • Signal Timestamp: {signal.timestamp}")
        print(f"   • Direction: {signal.direction.value}")
        print(f"   • Confidence: {signal.confidence_score:.3f}")
        print(f"   • Entry Price: ${signal.entry_price:.2f}")
        
        # FVG Touch Details
        print(f"\n🎯 FVG Touch Details:")
        print(f"   • FVG Touch Time: {signal.liquidity_event.timestamp}")
        print(f"   • FVG Direction: {signal.liquidity_event.direction.value}")
        print(f"   • FVG Status: {signal.liquidity_event.status}")
        print(f"   • FVG Price: ${signal.liquidity_event.price:.2f}")
        
        # Technical Signal (EMA Crossover) Details
        if signal.technical_signals:
            tech_signal = signal.technical_signals[0]
            print(f"\n📊 EMA Crossover Details:")
            print(f"   • Crossover Time: {tech_signal.timestamp}")
            print(f"   • Crossover Direction: {tech_signal.direction.value}")
            print(f"   • Crossover Confidence: {tech_signal.confidence:.3f}")
            print(f"   • Price at Crossover: ${tech_signal.values['price']:.2f}")
            print(f"   • EMA Fast (9): {tech_signal.values['ema_fast']:.2f}")
            print(f"   • EMA Slow (20): {tech_signal.values['ema_slow']:.2f}")
            print(f"   • EMA Separation: {abs(tech_signal.values['ema_fast'] - tech_signal.values['ema_slow']):.2f}")
        
        # Timing Analysis
        fvg_time = signal.liquidity_event.timestamp
        swing_time = signal.timestamp
        if signal.technical_signals:
            crossover_time = signal.technical_signals[0].timestamp
            
            print(f"\n⏰ Timing Analysis:")
            print(f"   • FVG Touch: {fvg_time}")
            print(f"   • Swing Point: {swing_time}")
            print(f"   • EMA Crossover: {crossover_time}")
            
            # Calculate time differences (simplified)
            try:
                import pandas as pd
                fvg_dt = pd.to_datetime(fvg_time, utc=True)
                swing_dt = pd.to_datetime(swing_time, utc=True)
                crossover_dt = pd.to_datetime(crossover_time, utc=True)
                
                swing_delay = (swing_dt - fvg_dt).total_seconds() / 60  # minutes
                crossover_delay = (crossover_dt - fvg_dt).total_seconds() / 60  # minutes
                
                print(f"   • Swing formed: {swing_delay:.0f} minutes after FVG touch")
                print(f"   • Crossover occurred: {crossover_delay:.0f} minutes after FVG touch")
            except:
                print(f"   • Timing calculation skipped (timezone issue)")
                pass
        
        # Chart Verification Instructions
        print(f"\n📈 Chart Verification Instructions:")
        print(f"   1. Open {symbol} chart on 15-minute timeframe")
        print(f"   2. Navigate to {fvg_time} (FVG touch)")
        print(f"   3. Add EMA 9 and EMA 20 indicators")
        print(f"   4. Verify:")
        print(f"      • FVG touch at {fvg_time}")
        print(f"      • Price forms {signal.direction.value} swing by {swing_time}")
        if signal.technical_signals:
            print(f"      • EMA 9 crosses {'above' if tech_signal.direction.value == 'bullish' else 'below'} EMA 20 at {crossover_time}")
            print(f"      • Price at crossover: ${tech_signal.values['price']:.2f}")
        
        print(f"\n" + "=" * 60 + "\n")
    
    # Summary for easy copying
    print(f"📋 QUICK REFERENCE FOR CHART VERIFICATION:")
    print("=" * 60)
    for i, signal in enumerate(signals):
        print(f"Signal #{i+1}:")
        print(f"  • FVG Touch: {signal.liquidity_event.timestamp} @ ${signal.liquidity_event.price:.2f}")
        print(f"  • Swing Point: {signal.timestamp} @ ${signal.entry_price:.2f}")
        if signal.technical_signals:
            tech_signal = signal.technical_signals[0]
            print(f"  • EMA Crossover: {tech_signal.timestamp} @ ${tech_signal.values['price']:.2f}")
            print(f"    EMA9: {tech_signal.values['ema_fast']:.2f}, EMA20: {tech_signal.values['ema_slow']:.2f}")
        print()
    
    print(f"✅ Analysis Complete!")
    db.close()


if __name__ == "__main__":
    get_detailed_signal_analysis()
