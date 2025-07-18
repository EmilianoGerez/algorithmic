#!/usr/bin/env python3
"""
Refactored Backtrader Test - Using Core Modules
Test backtrader integration with our existing core modules (properly)
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

# Import our working system
from working_clean_backtesting import WorkingCleanBacktester


class CoreModulesBacktraderStrategy(bt.Strategy):
    """
    Backtrader strategy that uses our core modules through WorkingCleanBacktester
    This is the proper way to integrate: delegate to existing proven system
    """
    
    params = (
        ('debug', True),
        ('starting_capital', 10000),
        ('risk_per_trade', 0.02),
        ('reward_risk_ratio', 2.0),
    )
    
    def __init__(self):
        # Initialize working system
        self.working_backtester = WorkingCleanBacktester()
        
        # Track signals and trades
        self.signals = []
        self.trades = []
        self.working_signals = []
        self.current_position = None
        
        # Get working system signals (this is where the magic happens)
        self._get_working_signals()
        
        if self.params.debug:
            print(f"🔧 Core Modules Strategy initialized")
            print(f"   📊 Working system signals: {len(self.working_signals)}")
    
    def _get_working_signals(self):
        """Get signals from our working system"""
        try:
            # Use exact same parameters as working system
            working_results = self.working_backtester.backtest_working(
                symbol="BTC/USD",
                ltf="5T",
                start="2025-05-18T00:00:00Z",
                end="2025-06-18T23:59:59Z"
            )
            
            if "error" not in working_results:
                self.working_signals = working_results['signals']
                if self.params.debug:
                    print(f"   ✅ Loaded {len(self.working_signals)} signals from working system")
            else:
                print(f"   ❌ Error loading signals: {working_results['error']}")
                
        except Exception as e:
            print(f"   ❌ Error getting working signals: {e}")
            self.working_signals = []
    
    def next(self):
        """Main strategy logic - uses working system signals"""
        current_time = self.data.datetime.datetime()
        
        # Check if we have a signal for this time
        for signal in self.working_signals:
            signal_time = signal['timestamp']
            
            # Convert signal time to datetime if needed
            if isinstance(signal_time, str):
                signal_time = pd.to_datetime(signal_time, utc=True)
            elif hasattr(signal_time, 'to_pydatetime'):
                signal_time = signal_time.to_pydatetime()
            
            # Ensure both times are timezone-aware or both are naive
            if signal_time.tzinfo is not None and current_time.tzinfo is None:
                current_time = pytz.utc.localize(current_time)
            elif signal_time.tzinfo is None and current_time.tzinfo is not None:
                signal_time = pytz.utc.localize(signal_time)
            
            # Check if signal time matches current time (within 5 minutes)
            time_diff = abs((current_time - signal_time).total_seconds())
            
            if time_diff <= 300:  # 5 minutes tolerance
                # Execute signal
                if signal['direction'] == 'bullish' and not self.position:
                    self.buy()
                    self.signals.append(signal)
                    if self.params.debug:
                        print(f"   🟢 BULLISH signal at {current_time}: {signal['entry_price']:.2f}")
                        
                elif signal['direction'] == 'bearish' and not self.position:
                    self.sell()
                    self.signals.append(signal)
                    if self.params.debug:
                        print(f"   🔴 BEARISH signal at {current_time}: {signal['entry_price']:.2f}")
    
    def notify_trade(self, trade):
        """Track completed trades"""
        if trade.isclosed:
            self.trades.append({
                'entry_price': trade.price,
                'exit_price': trade.price,
                'pnl': trade.pnl,
                'size': trade.size
            })
            if self.params.debug:
                print(f"   📊 Trade closed: PnL=${trade.pnl:.2f}")
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'working_backtester'):
            self.working_backtester.cleanup()


def run_core_modules_backtrader_test():
    """Run backtrader test using our core modules"""
    print("🎯 CORE MODULES BACKTRADER TEST")
    print("=" * 60)
    
    if not BACKTRADER_AVAILABLE:
        print("❌ Backtrader not available. Install with: pip install backtrader")
        return
    
    # 1. Get data from working system (this also flushes the DB)
    print("📊 Getting data from working system (with DB flush)...")
    backtester = WorkingCleanBacktester()
    
    try:
        # Use exact same parameters as working system
        working_results = backtester.backtest_working(
            symbol="BTC/USD",
            ltf="5T",
            start="2025-05-18T00:00:00Z",
            end="2025-06-18T23:59:59Z"
        )
        
        if "error" in working_results:
            print(f"❌ Error getting data: {working_results['error']}")
            return
        
        # Get raw data for Backtrader
        from src.services.signal_detection import SignalDetectionService
        from src.infrastructure.data.alpaca import AlpacaCryptoRepository
        from src.infrastructure.cache.redis import get_redis_connection
        from src.db.session import SessionLocal
        
        repo = AlpacaCryptoRepository()
        redis = get_redis_connection()
        db = SessionLocal()
        service = SignalDetectionService(repo, redis, db)
        
        # Get LTF data
        ltf_result = service.detect_signals(
            symbol="BTC/USD",
            signal_type="pivot",
            timeframe="5T",
            start="2025-05-18T00:00:00Z",
            end="2025-06-18T23:59:59Z"
        )
        ltf_candles = ltf_result["candles"]
        
        print(f"   📊 LTF Data: {len(ltf_candles)} candles")
        print(f"   📈 FVGs from working system: {len(working_results['fvgs_detected'])}")
        print(f"   🎯 Working system signals: {len(working_results['signals'])}")
        
        # 2. Setup Backtrader
        print("\\n🔧 Setting up Backtrader...")
        
        # Prepare data
        ltf_df = pd.DataFrame(ltf_candles)
        ltf_df['timestamp'] = pd.to_datetime(ltf_df['timestamp'], utc=True)
        ltf_df = ltf_df.sort_values('timestamp').reset_index(drop=True)
        ltf_df.set_index('timestamp', inplace=True)
        
        # Create Backtrader cerebro
        cerebro = bt.Cerebro()
        
        # Add our core modules strategy
        cerebro.addstrategy(CoreModulesBacktraderStrategy, debug=True)
        
        # Add data feed
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
        
        # Set broker
        cerebro.broker.setcash(10000)
        cerebro.broker.setcommission(commission=0.001)
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        
        print(f"💰 Starting Capital: ${cerebro.broker.getvalue():,.2f}")
        
        # 3. Run backtest
        print("\\n🏃 Running Backtrader with Core Modules...")
        print("-" * 50)
        
        results = cerebro.run()
        strat = results[0]
        
        final_value = cerebro.broker.getvalue()
        
        print("-" * 50)
        print(f"\\n📊 BACKTRADER RESULTS:")
        print("=" * 40)
        print(f"💰 Final Capital: ${final_value:,.2f}")
        print(f"📈 Total Return: {((final_value - 10000) / 10000) * 100:.2f}%")
        print(f"💡 Net Profit: ${final_value - 10000:,.2f}")
        
        # Show results
        print(f"\\n🎯 SIGNALS GENERATED: {len(strat.signals)}")
        print(f"🔄 TRADES COMPLETED: {len(strat.trades)}")
        
        # Show first few signals
        if strat.signals:
            print(f"\\n📊 First 5 signals:")
            for i, signal in enumerate(strat.signals[:5]):
                ny_tz = pytz.timezone('America/New_York')
                signal_time = signal['timestamp']
                if isinstance(signal_time, str):
                    signal_time = pd.to_datetime(signal_time)
                
                if signal_time.tzinfo is None:
                    utc_time = pytz.utc.localize(signal_time)
                else:
                    utc_time = signal_time.astimezone(pytz.utc)
                    
                ny_time = utc_time.astimezone(ny_tz)
                
                print(f"   {i+1}. {ny_time.strftime('%Y-%m-%d %H:%M')} | "
                      f"{signal['direction'].upper()} @ ${signal['entry_price']:.2f} | "
                      f"FVG: {signal['fvg_zone']} ({signal['fvg_timeframe']})")
        
        # Compare with working system
        print(f"\\n📊 COMPARISON:")
        print(f"   Working System: {len(working_results['signals'])} signals")
        print(f"   Backtrader:     {len(strat.signals)} signals")
        print(f"   Signal Match:   {len(strat.signals) / len(working_results['signals']) * 100:.1f}%")
        
        # Cleanup
        db.close()
        strat.cleanup()
        
        print(f"\\n✅ CORE MODULES INTEGRATION SUCCESS!")
        print(f"🎯 Backtrader is now using our existing core modules")
        print(f"🛠️ Single codebase maintenance achieved")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        backtester.cleanup()


if __name__ == "__main__":
    run_core_modules_backtrader_test()
