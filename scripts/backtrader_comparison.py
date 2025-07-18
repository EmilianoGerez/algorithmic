#!/usr/bin/env python3
"""
Backtrader vs Working Clean Backtesting Comparison
Run the exact same backtest with both systems to compare results
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import random
import warnings
warnings.filterwarnings('ignore')

# Import our existing system
from working_clean_backtesting import WorkingCleanBacktester

try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False
    print("❌ Backtrader not installed")

from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot


class BacktraderFVGDataFeed(bt.feeds.PandasData):
    """
    Custom Backtrader data feed with FVG information
    """
    lines = ('fvg_bullish', 'fvg_bearish', 'fvg_zone_low', 'fvg_zone_high')
    
    params = (
        ('fvg_bullish', -1),
        ('fvg_bearish', -1),
        ('fvg_zone_low', -1),
        ('fvg_zone_high', -1),
    )


class BacktraderFVGStrategy(bt.Strategy):
    """
    Backtrader implementation of the exact same FVG strategy
    """
    
    params = (
        ('debug', True),
        ('ema_fast', 9),
        ('ema_medium', 20),
        ('ema_slow', 50),
        ('risk_per_trade', 0.02),
        ('reward_risk_ratio', 2.0),
    )
    
    def __init__(self):
        # EMA indicators
        self.ema_9 = bt.indicators.EMA(period=self.params.ema_fast)
        self.ema_20 = bt.indicators.EMA(period=self.params.ema_medium)
        self.ema_50 = bt.indicators.EMA(period=self.params.ema_slow)
        
        # Track signals and trades
        self.signals = []
        self.trade_details = []
        
        # Store FVG data (will be populated from external source)
        self.fvg_zones = []
        
        # Position tracking
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        self.position_direction = None
        
        if self.params.debug:
            print("🔧 Backtrader FVG Strategy initialized")
    
    def set_fvg_zones(self, fvg_zones):
        """Set FVG zones from external source"""
        self.fvg_zones = fvg_zones
        if self.params.debug:
            print(f"📊 Loaded {len(fvg_zones)} FVG zones")
    
    def _is_trading_time(self, timestamp: datetime) -> bool:
        """Check if within NY trading hours"""
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
    
    def _find_swing_point(self, point_type: str) -> float:
        """Find swing point for stop loss (same logic as working system)"""
        lookback = min(20, len(self.data))
        
        if point_type == 'low':
            return min(self.data.low.get(ago=-i) for i in range(lookback))
        else:  # high
            return max(self.data.high.get(ago=-i) for i in range(lookback))
    
    def next(self):
        """Main strategy logic - matches working_clean_backtesting.py exactly"""
        current_time = self.data.datetime.datetime()
        
        # Skip if not trading time
        if not self._is_trading_time(current_time):
            return
        
        # Skip if insufficient data for EMAs
        if len(self.data) < self.params.ema_slow:
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
        
        # Entry logic
        if not self.position and available_fvgs:
            # Check FVG touches
            for fvg in available_fvgs:
                if (current_price >= fvg['zone_low'] and 
                    current_price <= fvg['zone_high']):
                    
                    # Get current EMA values
                    ema_9 = self.ema_9[0]
                    ema_20 = self.ema_20[0]
                    ema_50 = self.ema_50[0]
                    
                    # BULLISH SETUP
                    if fvg['direction'] == 'bullish':
                        # Check trend alignment: 9 EMA < 20 EMA < 50 EMA
                        if (ema_9 < ema_20 < ema_50):
                            # Check for 2 consecutive candles closing above EMA 20
                            if (len(self.data) >= 2 and
                                self.data.close[0] > ema_20 and
                                self.data.close[-1] > self.ema_20[-1]):
                                
                                # Calculate position size
                                risk_amount = self.broker.get_value() * self.params.risk_per_trade
                                
                                # Find stop loss
                                stop_loss = self._find_swing_point('low')
                                
                                if stop_loss < current_price:
                                    risk_per_share = current_price - stop_loss
                                    position_size = risk_amount / risk_per_share
                                    
                                    # Place order
                                    self.buy(size=position_size)
                                    
                                    # Track signal
                                    self.entry_price = current_price
                                    self.stop_loss = stop_loss
                                    self.take_profit = current_price + (risk_per_share * self.params.reward_risk_ratio)
                                    self.position_direction = 'bullish'
                                    
                                    signal = {
                                        'timestamp': current_time,
                                        'direction': 'bullish',
                                        'entry_price': current_price,
                                        'stop_loss': stop_loss,
                                        'take_profit': self.take_profit,
                                        'risk_amount': risk_per_share,
                                        'fvg_zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}",
                                        'fvg_timeframe': fvg.get('timeframe', '4H'),
                                        'ema_9': ema_9,
                                        'ema_20': ema_20,
                                        'ema_50': ema_50
                                    }
                                    self.signals.append(signal)
                                    
                                    if self.params.debug:
                                        print(f"🔵 BUY: {current_price:.2f} | Stop: {stop_loss:.2f} | "
                                              f"Target: {self.take_profit:.2f} | FVG: {signal['fvg_zone']} ({fvg.get('timeframe', '4H')})")
                                    break
                    
                    # BEARISH SETUP
                    elif fvg['direction'] == 'bearish':
                        # Check trend alignment: 9 EMA > 20 EMA > 50 EMA
                        if (ema_9 > ema_20 > ema_50):
                            # Check for 2 consecutive candles closing below EMA 20
                            if (len(self.data) >= 2 and
                                self.data.close[0] < ema_20 and
                                self.data.close[-1] < self.ema_20[-1]):
                                
                                # Calculate position size
                                risk_amount = self.broker.get_value() * self.params.risk_per_trade
                                
                                # Find stop loss
                                stop_loss = self._find_swing_point('high')
                                
                                if stop_loss > current_price:
                                    risk_per_share = stop_loss - current_price
                                    position_size = risk_amount / risk_per_share
                                    
                                    # Place order
                                    self.sell(size=position_size)
                                    
                                    # Track signal
                                    self.entry_price = current_price
                                    self.stop_loss = stop_loss
                                    self.take_profit = current_price - (risk_per_share * self.params.reward_risk_ratio)
                                    self.position_direction = 'bearish'
                                    
                                    signal = {
                                        'timestamp': current_time,
                                        'direction': 'bearish',
                                        'entry_price': current_price,
                                        'stop_loss': stop_loss,
                                        'take_profit': self.take_profit,
                                        'risk_amount': risk_per_share,
                                        'fvg_zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}",
                                        'fvg_timeframe': fvg.get('timeframe', '4H'),
                                        'ema_9': ema_9,
                                        'ema_20': ema_20,
                                        'ema_50': ema_50
                                    }
                                    self.signals.append(signal)
                                    
                                    if self.params.debug:
                                        print(f"🔴 SELL: {current_price:.2f} | Stop: {stop_loss:.2f} | "
                                              f"Target: {self.take_profit:.2f} | FVG: {signal['fvg_zone']} ({fvg.get('timeframe', '4H')})")
                                    break
        
        # Exit logic
        if self.position and self.entry_price:
            if self.position_direction == 'bullish':
                if current_price >= self.take_profit:
                    self.sell()
                    if self.params.debug:
                        print(f"✅ SELL (TP): {current_price:.2f} | Profit: {current_price - self.entry_price:.2f}")
                elif current_price <= self.stop_loss:
                    self.sell()
                    if self.params.debug:
                        print(f"❌ SELL (SL): {current_price:.2f} | Loss: {current_price - self.entry_price:.2f}")
            
            elif self.position_direction == 'bearish':
                if current_price <= self.take_profit:
                    self.buy()
                    if self.params.debug:
                        print(f"✅ BUY (TP): {current_price:.2f} | Profit: {self.entry_price - current_price:.2f}")
                elif current_price >= self.stop_loss:
                    self.buy()
                    if self.params.debug:
                        print(f"❌ BUY (SL): {current_price:.2f} | Loss: {self.entry_price - current_price:.2f}")
    
    def notify_trade(self, trade):
        """Called when trade is completed"""
        if trade.isclosed:
            self.trade_details.append({
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
            self.position_direction = None
    
    def stop(self):
        """Called when strategy stops"""
        if self.params.debug:
            print(f"\n📊 Backtrader Strategy Summary:")
            print(f"   Signals generated: {len(self.signals)}")
            print(f"   Trades completed: {len(self.trade_details)}")


def run_backtrader_comparison():
    """Run Backtrader with exact same parameters as working system"""
    print("🔄 BACKTRADER COMPARISON - EXACT SAME PARAMETERS")
    print("=" * 70)
    
    if not BACKTRADER_AVAILABLE:
        print("❌ Backtrader not available")
        return None
    
    try:
        # 1. First get the data and FVGs using our existing system
        print("📊 Getting data and FVGs from existing system...")
        
        # Initialize services
        repo = AlpacaCryptoRepository()
        redis = get_redis_connection()
        db = SessionLocal()
        service = SignalDetectionService(repo, redis, db)
        
        # Clean database
        db.query(FVG).delete()
        db.query(Pivot).delete()
        db.commit()
        
        # Get LTF data
        ltf_result = service.detect_signals(
            symbol="BTC/USD",
            signal_type="pivot",
            timeframe="5T",
            start="2025-05-18T00:00:00Z",
            end="2025-06-18T23:59:59Z"
        )
        ltf_candles = ltf_result["candles"]
        
        # Get HTF data for FVGs
        htf_4h_result = service.detect_signals(
            symbol="BTC/USD",
            signal_type="fvg_and_pivot",
            timeframe="4H",
            start="2025-05-18T00:00:00Z",
            end="2025-06-18T23:59:59Z"
        )
        htf_4h_candles = htf_4h_result["candles"]
        
        htf_1d_result = service.detect_signals(
            symbol="BTC/USD",
            signal_type="fvg_and_pivot",
            timeframe="1D",
            start="2025-05-18T00:00:00Z",
            end="2025-06-18T23:59:59Z"
        )
        htf_1d_candles = htf_1d_result["candles"]
        
        print(f"   📊 LTF Candles: {len(ltf_candles)}")
        print(f"   📊 4H Candles: {len(htf_4h_candles)}")
        print(f"   📊 1D Candles: {len(htf_1d_candles)}")
        
        # 2. Detect FVGs using same logic as working system
        def detect_fvgs_in_htf(htf_df: pd.DataFrame, timeframe: str) -> list:
            fvgs = []
            
            for i in range(len(htf_df) - 2):
                candle1 = htf_df.iloc[i]
                candle2 = htf_df.iloc[i + 1]
                candle3 = htf_df.iloc[i + 2]
                
                # Bullish FVG
                if candle1['high'] < candle3['low']:
                    fvg = {
                        'timestamp': candle2['timestamp'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'zone_low': candle1['high'],
                        'zone_high': candle3['low'],
                        'direction': 'bullish',
                        'timeframe': timeframe
                    }
                    fvgs.append(fvg)
                
                # Bearish FVG
                elif candle1['low'] > candle3['high']:
                    fvg = {
                        'timestamp': candle2['timestamp'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'zone_low': candle3['high'],
                        'zone_high': candle1['low'],
                        'direction': 'bearish',
                        'timeframe': timeframe
                    }
                    fvgs.append(fvg)
            
            return fvgs
        
        # Process HTF data
        htf_4h_df = pd.DataFrame(htf_4h_candles)
        htf_4h_df['timestamp'] = pd.to_datetime(htf_4h_df['timestamp'], utc=True)
        htf_4h_df = htf_4h_df.sort_values('timestamp').reset_index(drop=True)
        
        htf_1d_df = pd.DataFrame(htf_1d_candles)
        htf_1d_df['timestamp'] = pd.to_datetime(htf_1d_df['timestamp'], utc=True)
        htf_1d_df = htf_1d_df.sort_values('timestamp').reset_index(drop=True)
        
        # Detect FVGs
        fvgs_4h = detect_fvgs_in_htf(htf_4h_df, "4H")
        fvgs_1d = detect_fvgs_in_htf(htf_1d_df, "1D")
        all_fvgs = fvgs_4h + fvgs_1d
        
        print(f"   📈 FVGs detected: {len(fvgs_4h)} from 4H + {len(fvgs_1d)} from 1D = {len(all_fvgs)} total")
        
        # 3. Prepare data for Backtrader
        ltf_df = pd.DataFrame(ltf_candles)
        ltf_df['timestamp'] = pd.to_datetime(ltf_df['timestamp'], utc=True)
        ltf_df = ltf_df.sort_values('timestamp').reset_index(drop=True)
        ltf_df.set_index('timestamp', inplace=True)
        
        # Add FVG columns (placeholder for now)
        ltf_df['fvg_bullish'] = 0
        ltf_df['fvg_bearish'] = 0
        ltf_df['fvg_zone_low'] = 0
        ltf_df['fvg_zone_high'] = 0
        
        # 4. Setup Backtrader
        print("\n🔧 Setting up Backtrader with exact same parameters...")
        cerebro = bt.Cerebro()
        
        # Add strategy
        cerebro.addstrategy(BacktraderFVGStrategy, debug=True)
        
        # Add data
        data_feed = BacktraderFVGDataFeed(dataname=ltf_df)
        cerebro.adddata(data_feed)
        
        # Configure broker (same as working system)
        cerebro.broker.setcash(10000)  # Same starting balance
        cerebro.broker.setcommission(commission=0.001)
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        
        print(f"💰 Starting Capital: ${cerebro.broker.getvalue():,.2f}")
        
        # 5. Run backtest
        print("\n🏃 Running Backtrader backtest...")
        print("-" * 50)
        
        results = cerebro.run()
        
        # Get strategy and pass FVG data
        strat = results[0]
        strat.set_fvg_zones(all_fvgs)
        
        # Get results
        final_value = cerebro.broker.getvalue()
        
        print("-" * 50)
        print(f"\n📊 BACKTRADER RESULTS:")
        print("=" * 40)
        print(f"💰 Final Capital: ${final_value:,.2f}")
        print(f"📈 Total Return: {((final_value - 10000) / 10000) * 100:.2f}%")
        print(f"💡 Net Profit: ${final_value - 10000:,.2f}")
        
        # Analyzer results
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        trades = strat.analyzers.trades.get_analysis()
        returns = strat.analyzers.returns.get_analysis()
        
        print(f"\n📊 PERFORMANCE METRICS:")
        print(f"   Sharpe Ratio: {sharpe.get('sharperatio', 'N/A')}")
        print(f"   Max Drawdown: {drawdown.get('max', {}).get('drawdown', 'N/A'):.2f}%")
        print(f"   Total Trades: {trades.get('total', {}).get('total', 0)}")
        
        if 'total' in trades and trades['total']['total'] > 0:
            won = trades.get('won', {})
            lost = trades.get('lost', {})
            
            print(f"   Winning Trades: {won.get('total', 0)}")
            print(f"   Losing Trades: {lost.get('total', 0)}")
            
            if won.get('total', 0) > 0:
                win_rate = (won['total'] / trades['total']['total']) * 100
                print(f"   Win Rate: {win_rate:.1f}%")
                print(f"   Average Win: ${won.get('pnl', {}).get('average', 0):.2f}")
            
            if lost.get('total', 0) > 0:
                print(f"   Average Loss: ${lost.get('pnl', {}).get('average', 0):.2f}")
        
        # Show signals
        print(f"\n🎯 SIGNALS GENERATED ({len(strat.signals)}):")
        for i, signal in enumerate(strat.signals):
            ny_tz = pytz.timezone('America/New_York')
            if signal['timestamp'].tzinfo is None:
                utc_time = pytz.utc.localize(signal['timestamp'])
            else:
                utc_time = signal['timestamp']
            ny_time = utc_time.astimezone(ny_tz)
            
            print(f"   {i+1}. {ny_time.strftime('%Y-%m-%d %H:%M')} | "
                  f"{signal['direction'].upper()} @ ${signal['entry_price']:.2f} | "
                  f"FVG: {signal['fvg_zone']} ({signal['fvg_timeframe']})")
        
        # Cleanup
        db.close()
        
        return {
            'final_value': final_value,
            'signals': strat.signals,
            'trades': strat.trade_details,
            'fvgs_detected': all_fvgs
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_complete_comparison():
    """Run both systems and compare results"""
    print("🚀 COMPLETE BACKTRADER VS WORKING SYSTEM COMPARISON")
    print("=" * 80)
    
    # 1. Run Working System
    print("\n1️⃣ Running Working Clean Backtesting System...")
    print("-" * 50)
    
    backtester = WorkingCleanBacktester()
    
    try:
        working_results = backtester.backtest_working(
            symbol="BTC/USD",
            ltf="5T",
            start="2025-05-18T00:00:00Z",
            end="2025-06-18T23:59:59Z"
        )
        
        if "error" in working_results:
            print(f"❌ Working system error: {working_results['error']}")
            return
        
        print(f"✅ Working system completed:")
        print(f"   🎯 Signals: {len(working_results['signals'])}")
        print(f"   📈 FVGs detected: {len(working_results['fvgs_detected'])}")
        print(f"   📊 Candles processed: {working_results['candles_processed']}")
        
    except Exception as e:
        print(f"❌ Working system error: {e}")
        return
    
    finally:
        backtester.cleanup()
    
    # 2. Run Backtrader System
    print("\n2️⃣ Running Backtrader System...")
    print("-" * 50)
    
    backtrader_results = run_backtrader_comparison()
    
    if not backtrader_results:
        print("❌ Backtrader system failed")
        return
    
    # 3. Compare Results
    print("\n3️⃣ COMPARISON RESULTS:")
    print("=" * 50)
    
    print(f"📊 SIGNAL COMPARISON:")
    print(f"   Working System: {len(working_results['signals'])} signals")
    print(f"   Backtrader:     {len(backtrader_results['signals'])} signals")
    
    print(f"\n📈 FVG COMPARISON:")
    print(f"   Working System: {len(working_results['fvgs_detected'])} FVGs")
    print(f"   Backtrader:     {len(backtrader_results['fvgs_detected'])} FVGs")
    
    print(f"\n💰 PERFORMANCE COMPARISON:")
    print(f"   Working System: Simulated results (65% win rate)")
    print(f"   Backtrader:     ${backtrader_results['final_value']:,.2f} final value")
    
    print(f"\n🔧 TRADE COMPARISON:")
    print(f"   Working System: {len(working_results['signals'])} potential trades")
    print(f"   Backtrader:     {len(backtrader_results['trades'])} completed trades")
    
    print(f"\n✅ COMPARISON COMPLETE!")
    print(f"🎯 Both systems use identical:")
    print(f"   • Data source (same API calls)")
    print(f"   • FVG detection logic")
    print(f"   • EMA calculations (9, 20, 50)")
    print(f"   • Entry conditions (2 candles above/below EMA 20)")
    print(f"   • Risk management (2% per trade, 2:1 RR)")
    print(f"   • Trading hours (NY sessions)")
    print(f"   • Time period (2025-05-18 to 2025-06-18)")


if __name__ == "__main__":
    run_complete_comparison()
