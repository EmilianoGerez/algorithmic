#!/usr/bin/env python3
"""
Focused Backtrader Implementation - Exact Logic Match
Fix the signal generation issue by properly implementing the working system logic
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

# Import existing system for data and FVG detection
from working_clean_backtesting import WorkingCleanBacktester


class FocusedFVGStrategy(bt.Strategy):
    """
    Focused Backtrader strategy that exactly replicates working system logic
    """
    
    params = (
        ('debug', True),
        ('starting_capital', 10000),
        ('risk_per_trade', 0.02),
        ('reward_risk_ratio', 2.0),
    )
    
    def __init__(self):
        # EMA indicators
        self.ema_9 = bt.indicators.EMA(period=9)
        self.ema_20 = bt.indicators.EMA(period=20)
        self.ema_50 = bt.indicators.EMA(period=50)
        
        # Track signals for analysis
        self.signals = []
        self.trades = []
        self.fvg_zones = []
        self.current_position = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        
        if self.params.debug:
            print("🔧 Focused FVG Strategy initialized")
    
    def set_fvg_zones(self, fvg_zones):
        """Set FVG zones from external source"""
        self.fvg_zones = fvg_zones
        if self.params.debug:
            print(f"📊 Loaded {len(fvg_zones)} FVG zones")
    
    def _is_trading_time(self, timestamp: datetime) -> bool:
        """Check if within NY trading hours (same as working system)"""
        ny_tz = pytz.timezone('America/New_York')
        
        if timestamp.tzinfo is None:
            utc_timestamp = pytz.utc.localize(timestamp)
        else:
            utc_timestamp = timestamp.astimezone(pytz.utc)
        
        ny_time = utc_timestamp.astimezone(ny_tz)
        hour = ny_time.hour
        
        return (
            (20 <= hour <= 23) or  # 8 PM to 11 PM
            (hour == 0) or         # 12 AM
            (2 <= hour <= 3) or    # 2 AM to 3 AM
            (8 <= hour <= 12)      # 8 AM to 12 PM
        )
    
    def _find_swing_point(self, point_type: str, lookback: int = 20) -> float:
        """Find swing point for stop loss (same as working system)"""
        if len(self.data) < lookback:
            lookback = len(self.data)
        
        if point_type == 'low':
            return min(self.data.low.get(ago=-i) for i in range(lookback))
        else:  # high
            return max(self.data.high.get(ago=-i) for i in range(lookback))
    
    def next(self):
        """Main strategy logic - exact replica of working system"""
        current_time = self.data.datetime.datetime()
        
        # Skip if not trading time
        if not self._is_trading_time(current_time):
            return
        
        # Skip if insufficient data for EMAs
        if len(self.data) < 50:
            return
        
        current_price = self.data.close[0]
        
        # Get available FVGs at current time
        available_fvgs = []
        for fvg in self.fvg_zones:
            try:
                fvg_time = pd.to_datetime(fvg['timestamp'].replace('Z', ''), utc=True)
                if fvg_time <= current_time:
                    available_fvgs.append(fvg)
            except:
                continue
        
        if not available_fvgs:
            return
        
        # Get current EMA values
        ema_9 = self.ema_9[0]
        ema_20 = self.ema_20[0]
        ema_50 = self.ema_50[0]
        
        # Only process if we have position or can enter
        if not self.position:
            # Check each FVG for entry conditions
            for fvg in available_fvgs:
                # Check if price is touching FVG zone
                if (current_price >= fvg['zone_low'] and 
                    current_price <= fvg['zone_high']):
                    
                    # BULLISH SETUP
                    if fvg['direction'] == 'bullish':
                        # Check trend alignment: 9 EMA < 20 EMA < 50 EMA
                        if (ema_9 < ema_20 < ema_50):
                            # Check for 2 consecutive candles closing above EMA 20
                            if (len(self.data) >= 2 and
                                self.data.close[0] > ema_20 and
                                self.data.close[-1] > self.ema_20[-1]):
                                
                                # Calculate position
                                stop_loss = self._find_swing_point('low')
                                
                                if stop_loss < current_price:
                                    risk_per_share = current_price - stop_loss
                                    risk_amount = self.broker.get_value() * self.params.risk_per_trade
                                    position_size = risk_amount / risk_per_share
                                    
                                    # Place order
                                    self.buy(size=position_size)
                                    
                                    # Store signal details
                                    self.entry_price = current_price
                                    self.stop_loss = stop_loss
                                    self.take_profit = current_price + (risk_per_share * self.params.reward_risk_ratio)
                                    self.current_position = 'bullish'
                                    
                                    signal = {
                                        'timestamp': current_time,
                                        'direction': 'bullish',
                                        'entry_price': current_price,
                                        'stop_loss': stop_loss,
                                        'take_profit': self.take_profit,
                                        'fvg_zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}",
                                        'fvg_timeframe': fvg.get('timeframe', '4H'),
                                        'ema_9': ema_9,
                                        'ema_20': ema_20,
                                        'ema_50': ema_50
                                    }
                                    self.signals.append(signal)
                                    
                                    if self.params.debug:
                                        print(f"🔵 BUY: {current_price:.2f} | Stop: {stop_loss:.2f} | "
                                              f"Target: {self.take_profit:.2f} | FVG: {signal['fvg_zone']}")
                                    break
                    
                    # BEARISH SETUP
                    elif fvg['direction'] == 'bearish':
                        # Check trend alignment: 9 EMA > 20 EMA > 50 EMA
                        if (ema_9 > ema_20 > ema_50):
                            # Check for 2 consecutive candles closing below EMA 20
                            if (len(self.data) >= 2 and
                                self.data.close[0] < ema_20 and
                                self.data.close[-1] < self.ema_20[-1]):
                                
                                # Calculate position
                                stop_loss = self._find_swing_point('high')
                                
                                if stop_loss > current_price:
                                    risk_per_share = stop_loss - current_price
                                    risk_amount = self.broker.get_value() * self.params.risk_per_trade
                                    position_size = risk_amount / risk_per_share
                                    
                                    # Place order
                                    self.sell(size=position_size)
                                    
                                    # Store signal details
                                    self.entry_price = current_price
                                    self.stop_loss = stop_loss
                                    self.take_profit = current_price - (risk_per_share * self.params.reward_risk_ratio)
                                    self.current_position = 'bearish'
                                    
                                    signal = {
                                        'timestamp': current_time,
                                        'direction': 'bearish',
                                        'entry_price': current_price,
                                        'stop_loss': stop_loss,
                                        'take_profit': self.take_profit,
                                        'fvg_zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}",
                                        'fvg_timeframe': fvg.get('timeframe', '4H'),
                                        'ema_9': ema_9,
                                        'ema_20': ema_20,
                                        'ema_50': ema_50
                                    }
                                    self.signals.append(signal)
                                    
                                    if self.params.debug:
                                        print(f"🔴 SELL: {current_price:.2f} | Stop: {stop_loss:.2f} | "
                                              f"Target: {self.take_profit:.2f} | FVG: {signal['fvg_zone']}")
                                    break
        
        # Exit logic
        if self.position and self.entry_price:
            if self.current_position == 'bullish':
                if current_price >= self.take_profit:
                    self.sell()
                    if self.params.debug:
                        print(f"✅ SELL (TP): {current_price:.2f}")
                elif current_price <= self.stop_loss:
                    self.sell()
                    if self.params.debug:
                        print(f"❌ SELL (SL): {current_price:.2f}")
            
            elif self.current_position == 'bearish':
                if current_price <= self.take_profit:
                    self.buy()
                    if self.params.debug:
                        print(f"✅ BUY (TP): {current_price:.2f}")
                elif current_price >= self.stop_loss:
                    self.buy()
                    if self.params.debug:
                        print(f"❌ BUY (SL): {current_price:.2f}")
    
    def notify_trade(self, trade):
        """Called when trade is completed"""
        if trade.isclosed:
            self.trades.append({
                'pnl': trade.pnl,
                'pnlcomm': trade.pnlcomm,
                'size': trade.size,
                'price': trade.price,
                'value': trade.value,
                'commission': trade.commission,
                'datetime': self.data.datetime.datetime()
            })
            
            # Reset position tracking
            self.entry_price = None
            self.stop_loss = None
            self.take_profit = None
            self.current_position = None
    
    def stop(self):
        """Called when strategy stops"""
        if self.params.debug:
            print(f"\n📊 Backtrader Strategy Results:")
            print(f"   Signals generated: {len(self.signals)}")
            print(f"   Trades completed: {len(self.trades)}")


def run_focused_backtrader_test():
    """Run focused Backtrader test with exact same logic"""
    print("🎯 FOCUSED BACKTRADER TEST - EXACT LOGIC MATCH")
    print("=" * 60)
    
    if not BACKTRADER_AVAILABLE:
        print("❌ Backtrader not available")
        return
    
    # 1. Get same data as working system
    print("📊 Getting data from working system...")
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
        
        # 2. Setup Backtrader with exact same data
        print("\n🔧 Setting up Backtrader...")
        
        # Prepare data
        ltf_df = pd.DataFrame(ltf_candles)
        ltf_df['timestamp'] = pd.to_datetime(ltf_df['timestamp'], utc=True)
        ltf_df = ltf_df.sort_values('timestamp').reset_index(drop=True)
        ltf_df.set_index('timestamp', inplace=True)
        
        # Create Backtrader cerebro
        cerebro = bt.Cerebro()
        
        # Add strategy
        cerebro.addstrategy(FocusedFVGStrategy, debug=True)
        
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
        print("\n🏃 Running Backtrader backtest...")
        print("-" * 50)
        
        results = cerebro.run()
        strat = results[0]
        
        # Pass FVG zones to strategy
        strat.set_fvg_zones(working_results['fvgs_detected'])
        
        # Re-run with FVG zones
        print("\n🔄 Re-running with FVG zones...")
        cerebro = bt.Cerebro()
        cerebro.addstrategy(FocusedFVGStrategy, debug=True)
        cerebro.adddata(data_feed)
        cerebro.broker.setcash(10000)
        cerebro.broker.setcommission(commission=0.001)
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        
        # Custom strategy instance to pass FVG zones
        class PreloadedFVGStrategy(FocusedFVGStrategy):
            def __init__(self):
                super().__init__()
                self.fvg_zones = working_results['fvgs_detected']
                print(f"📊 Preloaded {len(self.fvg_zones)} FVG zones")
        
        cerebro.addstrategy(PreloadedFVGStrategy, debug=True)
        
        results = cerebro.run()
        strat = results[0]
        
        final_value = cerebro.broker.getvalue()
        
        print("-" * 50)
        print(f"\n📊 BACKTRADER RESULTS:")
        print("=" * 40)
        print(f"💰 Final Capital: ${final_value:,.2f}")
        print(f"📈 Total Return: {((final_value - 10000) / 10000) * 100:.2f}%")
        print(f"💡 Net Profit: ${final_value - 10000:,.2f}")
        
        # Show results
        print(f"\n🎯 SIGNALS GENERATED: {len(strat.signals)}")
        print(f"🔄 TRADES COMPLETED: {len(strat.trades)}")
        
        # Show first few signals
        if strat.signals:
            print(f"\n📊 First 5 signals:")
            for i, signal in enumerate(strat.signals[:5]):
                ny_tz = pytz.timezone('America/New_York')
                if signal['timestamp'].tzinfo is None:
                    utc_time = pytz.utc.localize(signal['timestamp'])
                else:
                    utc_time = signal['timestamp']
                ny_time = utc_time.astimezone(ny_tz)
                
                print(f"   {i+1}. {ny_time.strftime('%Y-%m-%d %H:%M')} | "
                      f"{signal['direction'].upper()} @ ${signal['entry_price']:.2f} | "
                      f"FVG: {signal['fvg_zone']} ({signal['fvg_timeframe']})")
        
        # Compare with working system
        print(f"\n📊 COMPARISON:")
        print(f"   Working System: {len(working_results['signals'])} signals")
        print(f"   Backtrader:     {len(strat.signals)} signals")
        
        # Cleanup
        db.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        backtester.cleanup()


if __name__ == "__main__":
    run_focused_backtrader_test()
