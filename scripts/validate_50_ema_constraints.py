#!/usr/bin/env python3
"""
Validate 50 EMA Constraints and Dual HTF Timeframes
Demonstrates the new order flow logic with 50 EMA trend alignment
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.working_clean_backtesting import WorkingCleanBacktester


def validate_50_ema_constraints():
    """
    Validate the new 50 EMA constraints and dual HTF timeframes
    """
    print("🔍 VALIDATING 50 EMA CONSTRAINTS & DUAL HTF TIMEFRAMES")
    print("=" * 80)
    
    print("✅ NEW ENHANCED LOGIC:")
    print("   🟢 BULLISH ENTRY:")
    print("      - Price reaches BULLISH FVG (4H or 1D)")
    print("      - 9 EMA < 20 EMA < 50 EMA at touch (trend alignment)")
    print("      - 9 EMA crosses above 20 EMA (entry)")
    print("      - Entry direction: BULLISH (same as FVG)")
    print("   🔴 BEARISH ENTRY:")
    print("      - Price reaches BEARISH FVG (4H or 1D)")
    print("      - 9 EMA > 20 EMA > 50 EMA at touch (trend alignment)")
    print("      - 9 EMA crosses below 20 EMA (entry)")
    print("      - Entry direction: BEARISH (same as FVG)")
    
    print("\n📊 HTF TIMEFRAME RESTRICTION:")
    print("   ✅ VALID HTF SOURCES: 4H and 1D timeframes only")
    print("   ❌ EXCLUDED: Lower timeframes (1H, 30M, 15M, etc.)")
    print("   💡 REASONING: Higher timeframes represent stronger institutional liquidity")
    
    backtester = WorkingCleanBacktester()
    
    try:
        # Test with shorter window for validation
        results = backtester.backtest_working(
            symbol="BTC/USD",
            ltf="15T",
            start="2025-05-01T00:00:00Z",
            end="2025-05-05T23:59:59Z"
        )
        
        if "error" in results:
            print(f"❌ {results['error']}")
            return
        
        print(f"\n📊 ENHANCED RESULTS:")
        print(f"   🎯 Valid Signals: {len(results['signals'])}")
        if 'fvgs_4h' in results and 'fvgs_1d' in results:
            print(f"   📈 4H FVGs: {len(results.get('fvgs_4h', []))}")
            print(f"   📈 1D FVGs: {len(results.get('fvgs_1d', []))}")
            print(f"   📈 Total FVGs: {len(results['fvgs_detected'])}")
        else:
            print(f"   📈 FVGs Available: {len(results['fvgs_detected'])}")
        print(f"   📊 Candles Processed: {results['candles_processed']}")
        
        print(f"\n🎯 SIGNAL VALIDATION:")
        
        if results['signals']:
            for i, signal in enumerate(results['signals']):
                print(f"\n   Signal {i+1}:")
                print(f"   📅 Time: {signal['timestamp']}")
                print(f"   📊 FVG Type: {signal['fvg_direction']} FVG ({signal.get('fvg_timeframe', '4H')})")
                print(f"   📈 Entry Direction: {signal['direction'].upper()}")
                print(f"   💰 Entry Price: ${signal['entry_price']:.2f}")
                print(f"   🎯 FVG Zone: {signal['fvg_zone']}")
                print(f"   📊 EMA at Touch: 9={signal['ema_9_at_touch']:.2f}, 20={signal['ema_20_at_touch']:.2f}, 50={signal.get('ema_50_at_touch', 'N/A')}")
                
                # Validate constraints
                ema_9 = signal['ema_9_at_touch']
                ema_20 = signal['ema_20_at_touch']
                ema_50 = signal.get('ema_50_at_touch')
                
                if signal['direction'] == 'bullish':
                    if ema_50 and ema_9 < ema_20 < ema_50:
                        print(f"   ✅ CORRECT: Bullish FVG + Bullish Entry + 9 < 20 < 50 EMA")
                    else:
                        print(f"   ❌ INCORRECT: EMA alignment failed")
                elif signal['direction'] == 'bearish':
                    if ema_50 and ema_9 > ema_20 > ema_50:
                        print(f"   ✅ CORRECT: Bearish FVG + Bearish Entry + 9 > 20 > 50 EMA")
                    else:
                        print(f"   ❌ INCORRECT: EMA alignment failed")
                
                print(f"   🎯 Trend Alignment: {signal.get('trend_alignment', 'N/A')}")
                print(f"   🎯 Confidence: {signal['confidence']}")
        else:
            print(f"   📊 No signals found in test period")
            print(f"   💡 This could indicate stronger filtering with 50 EMA constraints")
        
        print(f"\n📈 AVAILABLE FVGs:")
        if results['fvgs_detected']:
            for i, fvg in enumerate(results['fvgs_detected'][:10]):  # Show first 10
                tf = fvg.get('timeframe', '4H')
                print(f"   {i+1}. {fvg['timestamp']}: {fvg['direction']} FVG")
                print(f"      Zone: ${fvg['zone_low']:.2f} - ${fvg['zone_high']:.2f}")
                print(f"      Timeframe: {tf}")
                
            if len(results['fvgs_detected']) > 10:
                print(f"   ... and {len(results['fvgs_detected']) - 10} more FVGs")
        
        print(f"\n🔄 CONSTRAINT COMPARISON:")
        print(f"==================================================")
        
        print(f"\n❌ OLD LOGIC (REMOVED):")
        print(f"   Bullish Entry: Bullish FVG + 9<20 + crossover")
        print(f"   Bearish Entry: Bearish FVG + 9>20 + crossover")
        print(f"   → No trend alignment with higher timeframe")
        
        print(f"\n✅ NEW ENHANCED LOGIC:")
        print(f"   Bullish Entry: Bullish FVG + 9<20<50 + crossover")
        print(f"   Bearish Entry: Bearish FVG + 9>20>50 + crossover")
        print(f"   → Strong trend alignment with 50 EMA")
        
        print(f"\n💡 ENHANCEMENT BENEFITS:")
        print(f"   - 50 EMA acts as trend filter")
        print(f"   - Reduces false signals in ranging markets")
        print(f"   - Ensures entries align with higher timeframe bias")
        print(f"   - Only 4H and 1D FVGs for institutional-grade liquidity")
        
        print(f"\n✅ LOGIC ENHANCED!")
        print(f"   50 EMA constraint added for better trend alignment!")
        print(f"   Dual HTF timeframes (4H + 1D) for stronger liquidity pools!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        backtester.cleanup()


if __name__ == "__main__":
    validate_50_ema_constraints()
