#!/usr/bin/env python3
"""
Ultimate Debugging Implementation - Find the Root Cause
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import warnings
warnings.filterwarnings('ignore')

try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False

from working_clean_backtesting import WorkingCleanBacktester


class DebugFVGStrategy(bt.Strategy):
    """
    Debug version - Step by step signal detection
    """
    
    def __init__(self):
        # Initialize indicators
        self.ema_9 = bt.indicators.EMA(self.data.close, period=9)
        self.ema_20 = bt.indicators.EMA(self.data.close, period=20)
        self.ema_50 = bt.indicators.EMA(self.data.close, period=50)
        
        # State
        self.fvg_zones = []
        self.debug_data = []
        self.ny_tz = pytz.timezone('America/New_York')
        
        print("Debug Strategy initialized")
    
    def set_fvg_zones(self, fvg_zones):
        """Set FVG zones"""
        self.fvg_zones = fvg_zones
        print(f"Loaded {len(fvg_zones)} FVG zones:")
        for i, fvg in enumerate(fvg_zones[:5]):  # Show first 5
            print(f"  {i+1}. {fvg['timestamp']} | {fvg['direction']} | {fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}")
    
    def _is_trading_time(self, dt):
        """Check trading time"""
        if dt.tzinfo is None:
            utc_dt = pytz.utc.localize(dt)
        else:
            utc_dt = dt.astimezone(pytz.utc)
        
        ny_time = utc_dt.astimezone(self.ny_tz)
        hour = ny_time.hour
        
        return (
            (20 <= hour <= 23) or
            (hour == 0) or
            (2 <= hour <= 3) or
            (8 <= hour <= 12)
        )
    
    def next(self):
        """Debug next() method"""
        # Only debug every 100 candles to avoid spam
        if len(self.data) % 100 == 0:
            current_time = self.data.datetime.datetime(0)
            current_price = self.data.close[0]
            
            # Check trading time
            is_trading = self._is_trading_time(current_time)
            
            # Check FVG availability
            available_fvgs = []
            for fvg in self.fvg_zones:
                try:
                    fvg_time = pd.to_datetime(fvg['timestamp'].replace('Z', ''), utc=True)
                    if fvg_time <= current_time:
                        available_fvgs.append(fvg)
                except:
                    continue
            
            # Check FVG touches
            fvg_touches = []
            for fvg in available_fvgs:
                if (current_price <= fvg['zone_high'] and current_price >= fvg['zone_low']):
                    fvg_touches.append(fvg)
            
            # Check EMA values
            ema_9 = self.ema_9[0] if len(self.data) >= 9 else None
            ema_20 = self.ema_20[0] if len(self.data) >= 20 else None
            ema_50 = self.ema_50[0] if len(self.data) >= 50 else None
            
            # Debug output
            if len(self.data) >= 51:  # Only when we have enough data
                print(f"\n🔍 DEBUG {len(self.data)} @ {current_time} | Price: {current_price:.2f}")
                print(f"   Trading Time: {is_trading}")
                print(f"   Available FVGs: {len(available_fvgs)}")
                print(f"   FVG Touches: {len(fvg_touches)}")
                print(f"   EMA 9: {ema_9:.2f} | EMA 20: {ema_20:.2f} | EMA 50: {ema_50:.2f}")
                
                if fvg_touches:
                    print(f"   🎯 FVG TOUCHED: {fvg_touches[0]['direction']} zone {fvg_touches[0]['zone_low']:.2f}-{fvg_touches[0]['zone_high']:.2f}")
                    
                    # Check EMA alignment
                    fvg = fvg_touches[0]
                    if fvg['direction'] == 'bullish':
                        ema_aligned = ema_9 < ema_20 < ema_50
                        print(f"   📊 Bullish EMA Alignment: {ema_aligned} (9<20<50)")
                    else:
                        ema_aligned = ema_9 > ema_20 > ema_50
                        print(f"   📊 Bearish EMA Alignment: {ema_aligned} (9>20>50)")
                    
                    # Check consecutive closes
                    if len(self.data) >= 2:
                        current_close = self.data.close[0]
                        prev_close = self.data.close[-1]
                        current_ema20 = self.ema_20[0]
                        prev_ema20 = self.ema_20[-1]
                        
                        if fvg['direction'] == 'bullish':
                            consecutive = (current_close > current_ema20 and prev_close > prev_ema20)
                            print(f"   📈 Consecutive above EMA20: {consecutive}")
                        else:
                            consecutive = (current_close < current_ema20 and prev_close < prev_ema20)
                            print(f"   📉 Consecutive below EMA20: {consecutive}")
                        
                        if ema_aligned and consecutive:
                            print(f"   🚀 ALL CONDITIONS MET - SHOULD SIGNAL!")
                    
                    print(f"   " + "="*50)
    
    def stop(self):
        """Called when backtest ends"""
        print(f"\n📊 Debug Strategy Results:")
        print(f"   Total candles processed: {len(self.data)}")
        print(f"   FVG zones available: {len(self.fvg_zones)}")


def run_ultimate_debug():
    """Run ultimate debug to find root cause"""
    print("🔍 ULTIMATE DEBUG - FINDING ROOT CAUSE")
    print("=" * 60)
    
    if not BACKTRADER_AVAILABLE:
        print("❌ Backtrader not available")
        return
    
    try:
        # Get our system data first
        print("📊 Getting our system data...")
        backtester = WorkingCleanBacktester()
        
        results = backtester.backtest_working(
            symbol="BTC/USD",
            ltf="5T",
            start="2025-05-18T00:00:00Z",
            end="2025-06-18T23:59:59Z"
        )
        
        print(f"✅ Our system generated {len(results['signals'])} signals")
        print(f"✅ Our system detected {len(results['fvgs_detected'])} FVGs")
        
        # Show first few signals from our system
        print(f"\n📈 First 5 signals from our system:")
        for i, signal in enumerate(results['signals'][:5]):
            print(f"   {i+1}. {signal['timestamp']} | {signal['direction']} @ {signal['entry_price']:.2f}")
        
        # Get raw data for Backtrader
        print(f"\n🔧 Preparing Backtrader data...")
        
        from src.services.signal_detection import SignalDetectionService
        from src.infrastructure.data.alpaca import AlpacaCryptoRepository
        from src.infrastructure.cache.redis import get_redis_connection
        from src.db.session import SessionLocal
        
        repo = AlpacaCryptoRepository()
        redis = get_redis_connection()
        db = SessionLocal()
        service = SignalDetectionService(repo, redis, db)
        
        ltf_result = service.detect_signals(
            symbol="BTC/USD",
            signal_type="pivot",
            timeframe="5T",
            start="2025-05-18T00:00:00Z",
            end="2025-06-18T23:59:59Z"
        )
        
        ltf_df = pd.DataFrame(ltf_result["candles"])
        ltf_df['timestamp'] = pd.to_datetime(ltf_df['timestamp'], utc=True)
        ltf_df = ltf_df.sort_values('timestamp').reset_index(drop=True)
        ltf_df.set_index('timestamp', inplace=True)
        
        print(f"✅ Prepared {len(ltf_df)} candles for Backtrader")
        
        # Setup Backtrader with debug strategy
        print(f"\n🚀 Setting up Backtrader with debug strategy...")
        
        cerebro = bt.Cerebro()
        
        # Create debug strategy that will print step by step
        class PreloadedDebugStrategy(DebugFVGStrategy):
            def __init__(self):
                super().__init__()
                self.fvg_zones = results['fvgs_detected']
                print(f"Preloaded {len(self.fvg_zones)} FVG zones")
        
        cerebro.addstrategy(PreloadedDebugStrategy)
        
        # Add data
        data_feed = bt.feeds.PandasData(
            dataname=ltf_df,
            datetime=None,
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume'
        )
        cerebro.adddata(data_feed)
        
        # Configure broker
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.001)
        
        print(f"🏃 Running debug backtest...")
        print(f"   This will show step-by-step debugging every 100 candles")
        print(f"   Looking for FVG touches and signal conditions")
        print("-" * 60)
        
        # Run
        results_bt = cerebro.run()
        
        print(f"\n✅ Debug backtest complete!")
        
        # Cleanup
        db.close()
        backtester.cleanup()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_ultimate_debug()
