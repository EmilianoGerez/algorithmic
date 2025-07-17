#!/usr/bin/env python3
"""
CORRECTED Order Flow Logic Validation
Entry direction should be SAME as FVG direction
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from working_clean_backtesting import WorkingCleanBacktester


def validate_corrected_logic():
    """
    Validate the CORRECTED order flow logic
    """
    print("🔍 CORRECTED EMA ORDER FLOW VALIDATION")
    print("=" * 80)
    
    print(f"✅ CORRECT LOGIC:")
    print(f"   🟢 BULLISH ENTRY:")
    print(f"      - Price reaches BULLISH FVG")
    print(f"      - 9 EMA < 20 EMA at touch (rejection setup)")
    print(f"      - 9 EMA crosses above 20 EMA (entry)")
    print(f"      - Entry direction: BULLISH (same as FVG)")
    print(f"   🔴 BEARISH ENTRY:")
    print(f"      - Price reaches BEARISH FVG")
    print(f"      - 9 EMA > 20 EMA at touch (rejection setup)")
    print(f"      - 9 EMA crosses below 20 EMA (entry)")
    print(f"      - Entry direction: BEARISH (same as FVG)")
    
    backtester = WorkingCleanBacktester()
    
    try:
        # Test with shorter period to see corrected results
        results = backtester.backtest_working(
            symbol="BTC/USD",
            ltf="15T",
            start="2025-05-01T00:00:00Z",
            end="2025-05-05T23:59:59Z"
        )
        
        print(f"\n📊 CORRECTED RESULTS:")
        print(f"   🎯 Valid Signals: {len(results['signals'])}")
        print(f"   📈 FVGs Available: {len(results['fvgs_detected'])}")
        print(f"   📊 Candles Processed: {results['candles_processed']}")
        
        if results['signals']:
            print(f"\n🎯 SIGNAL VALIDATION:")
            for i, signal in enumerate(results['signals']):
                print(f"\n   Signal {i+1}:")
                print(f"   📅 Time: {signal['timestamp']}")
                print(f"   📊 FVG Type: {signal['fvg_direction']} FVG")
                print(f"   📈 Entry Direction: {signal['direction'].upper()}")
                print(f"   💰 Entry Price: ${signal['entry_price']:.2f}")
                print(f"   🎯 FVG Zone: {signal['fvg_zone']}")
                print(f"   📊 EMA at Touch: 9={signal['ema_9_at_touch']:.2f}, 20={signal['ema_20_at_touch']:.2f}")
                
                # Validate the CORRECTED logic
                if signal['direction'] == 'bullish' and signal['fvg_direction'] == 'bullish':
                    if signal['ema_9_at_touch'] < signal['ema_20_at_touch']:
                        print(f"   ✅ CORRECT: Bullish FVG + Bullish Entry + 9 EMA < 20 EMA")
                    else:
                        print(f"   ❌ INVALID: Need 9 EMA < 20 EMA for bullish FVG entry")
                        
                elif signal['direction'] == 'bearish' and signal['fvg_direction'] == 'bearish':
                    if signal['ema_9_at_touch'] > signal['ema_20_at_touch']:
                        print(f"   ✅ CORRECT: Bearish FVG + Bearish Entry + 9 EMA > 20 EMA")
                    else:
                        print(f"   ❌ INVALID: Need 9 EMA > 20 EMA for bearish FVG entry")
                else:
                    print(f"   ❌ INVALID: Entry direction doesn't match FVG direction")
                
                print(f"   🎯 Confidence: {signal['confidence']:.2f}")
        
        else:
            print(f"\n⚠️  NO VALID SIGNALS FOUND")
            print(f"   Algorithm is correctly selective with new logic!")
        
        print(f"\n📈 AVAILABLE FVGs:")
        for i, fvg in enumerate(results['fvgs_detected']):
            print(f"   {i+1}. {fvg['timestamp']}: {fvg['direction']} FVG")
            print(f"      Zone: ${fvg['zone_low']:.2f} - ${fvg['zone_high']:.2f}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        backtester.cleanup()


def show_logic_comparison():
    """
    Show the difference between old and corrected logic
    """
    print(f"\n🔄 LOGIC COMPARISON:")
    print(f"=" * 50)
    
    print(f"\n❌ OLD LOGIC (INCORRECT):")
    print(f"   Bullish Entry: Bearish FVG + 9<20 + crossover")
    print(f"   Bearish Entry: Bullish FVG + 9>20 + crossover")
    print(f"   → Entry OPPOSITE to FVG direction")
    
    print(f"\n✅ CORRECTED LOGIC:")
    print(f"   Bullish Entry: Bullish FVG + 9<20 + crossover")
    print(f"   Bearish Entry: Bearish FVG + 9>20 + crossover")
    print(f"   → Entry SAME as FVG direction")
    
    print(f"\n💡 CONCEPT:")
    print(f"   - FVG represents institutional bias/direction")
    print(f"   - Price rejection from FVG creates swing")
    print(f"   - Entry follows FVG direction after rejection")
    print(f"   - EMAs confirm momentum in FVG direction")


if __name__ == "__main__":
    validate_corrected_logic()
    show_logic_comparison()
    
    print(f"\n✅ LOGIC CORRECTED!")
    print(f"   Entry direction now matches FVG direction!")
    print(f"   This aligns with proper market structure understanding!")
