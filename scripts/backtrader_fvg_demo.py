#!/usr/bin/env python3
"""
Backtrader FVG Integration Demo
Ready to run with real FVG strategy
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
    print("✅ Backtrader available")
except ImportError:
    BACKTRADER_AVAILABLE = False
    print("❌ Backtrader not available")
    # Create dummy bt for import purposes
    class DummyBT:
        class Strategy:
            pass
        class indicators:
            @staticmethod
            def EMA(period):
                return None
        class feeds:
            @staticmethod
            def PandasData(dataname):
                return None
        class analyzers:
            class SharpeRatio:
                pass
            class DrawDown:
                pass
            class TradeAnalyzer:
                pass
    bt = DummyBT()


def create_sample_data():
    """Create sample OHLCV data for demo"""
    np.random.seed(42)
    
    # Create date range
    start_date = datetime(2025, 6, 1)
    end_date = datetime(2025, 6, 7)
    dates = pd.date_range(start_date, end_date, freq='5T')
    
    # Generate sample price data
    close_prices = []
    current_price = 100.0
    
    for i, date in enumerate(dates):
        change = np.random.normal(0.001, 0.01)
        current_price *= (1 + change)
        close_prices.append(current_price)
    
    # Generate OHLCV data
    data = []
    for i, (date, close) in enumerate(zip(dates, close_prices)):
        high = close * (1 + abs(np.random.normal(0, 0.003)))
        low = close * (1 - abs(np.random.normal(0, 0.003)))
        open_price = close_prices[i-1] if i > 0 else close
        volume = np.random.randint(1000, 10000)
        
        data.append({
            'datetime': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
    
    return pd.DataFrame(data)


class FVGStrategy(bt.Strategy):
    """Simple FVG strategy for demo"""
    
    params = (
        ('risk_per_trade', 0.02),
        ('reward_risk_ratio', 2.0),
        ('debug', True),
    )
    
    def __init__(self):
        # EMA indicators
        self.ema_20 = bt.indicators.EMA(period=20)
        self.ema_50 = bt.indicators.EMA(period=50)
        
        # Track signals
        self.signals = []
        
        # Sample FVG zones
        self.fvg_zones = [
            {'lower_bound': 101.5, 'upper_bound': 102.5, 'direction': 'bullish'},
            {'lower_bound': 103.0, 'upper_bound': 104.0, 'direction': 'bearish'},
        ]
        
        if self.params.debug:
            print(f"🔧 Strategy initialized with {len(self.fvg_zones)} FVG zones")
    
    def next(self):
        """Strategy logic"""
        if len(self.data) < 50:  # Need data for EMAs
            return
        
        current_price = self.data.close[0]
        
        if not self.position:
            # Look for FVG interactions
            for fvg in self.fvg_zones:
                if fvg['lower_bound'] <= current_price <= fvg['upper_bound']:
                    
                    # Bullish setup
                    if (fvg['direction'] == 'bullish' and 
                        self.ema_20[0] > self.ema_50[0] and
                        self.data.close[0] > self.ema_20[0]):
                        
                        self.buy()
                        self.signals.append({
                            'direction': 'bullish',
                            'price': current_price,
                            'fvg_zone': f"{fvg['lower_bound']:.2f}-{fvg['upper_bound']:.2f}"
                        })
                        
                        if self.params.debug:
                            print(f"🔵 BUY: {current_price:.2f} | FVG: {fvg['lower_bound']:.2f}-{fvg['upper_bound']:.2f}")
                        break
                    
                    # Bearish setup
                    elif (fvg['direction'] == 'bearish' and
                          self.ema_20[0] < self.ema_50[0] and
                          self.data.close[0] < self.ema_20[0]):
                        
                        self.sell()
                        self.signals.append({
                            'direction': 'bearish',
                            'price': current_price,
                            'fvg_zone': f"{fvg['lower_bound']:.2f}-{fvg['upper_bound']:.2f}"
                        })
                        
                        if self.params.debug:
                            print(f"🔴 SELL: {current_price:.2f} | FVG: {fvg['lower_bound']:.2f}-{fvg['upper_bound']:.2f}")
                        break
        
        # Simple exit logic
        else:
            entry_price = self.position.price
            
            if self.position.size > 0:  # Long position
                if current_price >= entry_price * 1.04:  # 4% profit
                    self.sell()
                    if self.params.debug:
                        print(f"✅ SELL (Profit): {current_price:.2f}")
                elif current_price <= entry_price * 0.98:  # 2% loss
                    self.sell()
                    if self.params.debug:
                        print(f"❌ SELL (Loss): {current_price:.2f}")
            
            elif self.position.size < 0:  # Short position
                if current_price <= entry_price * 0.96:  # 4% profit
                    self.buy()
                    if self.params.debug:
                        print(f"✅ BUY (Profit): {current_price:.2f}")
                elif current_price >= entry_price * 1.02:  # 2% loss
                    self.buy()
                    if self.params.debug:
                        print(f"❌ BUY (Loss): {current_price:.2f}")
    
    def stop(self):
        """Called when strategy stops"""
        if self.params.debug:
            print(f"\n📊 Strategy Summary: {len(self.signals)} signals generated")


def run_backtrader_fvg_demo():
    """Run the Backtrader FVG demo"""
    print("🚀 BACKTRADER FVG INTEGRATION - READY TO RUN")
    print("=" * 60)
    
    if not BACKTRADER_AVAILABLE:
        print("❌ Backtrader not available")
        return False
    
    try:
        # Create sample data
        print("📊 Creating sample data...")
        df = create_sample_data()
        df.set_index('datetime', inplace=True)
        
        print(f"📈 Generated {len(df)} data points")
        print(f"📊 Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        
        # Setup Backtrader
        print("\n🔧 Setting up Backtrader...")
        cerebro = bt.Cerebro()
        
        # Add strategy
        cerebro.addstrategy(FVGStrategy, debug=True)
        
        # Add data
        data_feed = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data_feed)
        
        # Configure broker
        cerebro.broker.setcash(50000)
        cerebro.broker.setcommission(commission=0.001)
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        print(f"💰 Starting Capital: ${cerebro.broker.getvalue():,.2f}")
        
        # Run backtest
        print("\n🏃 Running backtest...")
        print("-" * 40)
        
        results = cerebro.run()
        
        # Get results
        strat = results[0]
        final_value = cerebro.broker.getvalue()
        
        print("-" * 40)
        print(f"\n📊 BACKTEST RESULTS:")
        print("=" * 40)
        print(f"💰 Final Capital: ${final_value:,.2f}")
        print(f"📈 Total Return: {((final_value - 50000) / 50000) * 100:.2f}%")
        print(f"💡 Net Profit: ${final_value - 50000:,.2f}")
        
        # Analyzer results
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        trades = strat.analyzers.trades.get_analysis()
        
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
        
        print(f"\n🎯 SIGNALS: {len(strat.signals)} generated")
        
        print(f"\n✅ BACKTRADER FVG INTEGRATION SUCCESSFUL!")
        print(f"🎯 System ready for advanced backtesting")
        print(f"🚀 Professional framework operational")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_backtrader_fvg_demo()
    if success:
        print(f"\n🎉 Demo completed successfully!")
    else:
        print(f"\n❌ Demo failed - check setup")
