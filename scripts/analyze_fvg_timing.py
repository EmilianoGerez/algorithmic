#!/usr/bin/env python3
"""
Final Root Cause Analysis - FVG Timing Issue
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from working_clean_backtesting import WorkingCleanBacktester
import pandas as pd
import pytz

def analyze_fvg_timing():
    """Analyze FVG timing issue"""
    print("🔍 ROOT CAUSE ANALYSIS - FVG TIMING")
    print("=" * 50)
    
    # Get our system data
    backtester = WorkingCleanBacktester()
    
    results = backtester.backtest_working(
        symbol="BTC/USD",
        ltf="5T",
        start="2025-05-18T00:00:00Z",
        end="2025-06-18T23:59:59Z"
    )
    
    print(f"✅ Our system detected {len(results['fvgs_detected'])} FVGs")
    print(f"✅ First signal: {results['signals'][0]['timestamp']}")
    print(f"✅ Last signal: {results['signals'][-1]['timestamp']}")
    
    # Analyze FVG timestamps
    print(f"\n📊 FVG Analysis:")
    print(f"   Total FVGs: {len(results['fvgs_detected'])}")
    
    # Convert and sort FVG timestamps
    fvg_times = []
    for fvg in results['fvgs_detected']:
        try:
            fvg_time = pd.to_datetime(fvg['timestamp'].replace('Z', ''), utc=True)
            fvg_times.append({
                'timestamp': fvg_time,
                'direction': fvg['direction'],
                'timeframe': fvg.get('timeframe', '4H'),
                'zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}"
            })
        except:
            print(f"   ❌ Invalid FVG timestamp: {fvg['timestamp']}")
    
    # Sort by timestamp
    fvg_times.sort(key=lambda x: x['timestamp'])
    
    print(f"\n📈 FVG Timeline (First 10):")
    for i, fvg in enumerate(fvg_times[:10]):
        print(f"   {i+1}. {fvg['timestamp']} | {fvg['timeframe']} | {fvg['direction']} | {fvg['zone']}")
    
    # Check if FVGs are BEFORE backtest period
    backtest_start = pd.to_datetime("2025-05-18T00:00:00Z")
    backtest_end = pd.to_datetime("2025-06-18T23:59:59Z")
    
    fvgs_before = [fvg for fvg in fvg_times if fvg['timestamp'] < backtest_start]
    fvgs_during = [fvg for fvg in fvg_times if backtest_start <= fvg['timestamp'] <= backtest_end]
    fvgs_after = [fvg for fvg in fvg_times if fvg['timestamp'] > backtest_end]
    
    print(f"\n⏰ FVG Timing Analysis:")
    print(f"   Backtest period: {backtest_start} to {backtest_end}")
    print(f"   FVGs before backtest: {len(fvgs_before)}")
    print(f"   FVGs during backtest: {len(fvgs_during)}")
    print(f"   FVGs after backtest: {len(fvgs_after)}")
    
    if fvgs_before:
        print(f"\n❌ PROBLEM FOUND: FVGs created BEFORE backtest period!")
        print(f"   Latest FVG before backtest: {fvgs_before[-1]['timestamp']}")
        print(f"   This explains why Backtrader sees 0 available FVGs!")
    
    if fvgs_during:
        print(f"\n✅ FVGs during backtest period:")
        for fvg in fvgs_during:
            print(f"   - {fvg['timestamp']} | {fvg['timeframe']} | {fvg['direction']}")
    
    # Check signal timing
    signal_times = [pd.to_datetime(sig['timestamp']) for sig in results['signals']]
    earliest_signal = min(signal_times)
    latest_signal = max(signal_times)
    
    print(f"\n📊 Signal Timing:")
    print(f"   Earliest signal: {earliest_signal}")
    print(f"   Latest signal: {latest_signal}")
    
    # Check if signals use FVGs from before backtest
    print(f"\n🔍 Signal-FVG Relationship:")
    for i, signal in enumerate(results['signals'][:5]):
        signal_time = pd.to_datetime(signal['timestamp'])
        fvg_time = pd.to_datetime(signal['fvg_timestamp'].replace('Z', ''))
        
        print(f"   Signal {i+1}: {signal_time}")
        print(f"     Uses FVG from: {fvg_time}")
        print(f"     Time gap: {signal_time - fvg_time}")
        print(f"     FVG created {'BEFORE' if fvg_time < backtest_start else 'DURING'} backtest")
        print()
    
    backtester.cleanup()

if __name__ == "__main__":
    analyze_fvg_timing()
