#!/usr/bin/env python3
"""
Simple Backtrader Integration Test
Test the core Backtrader integration without full database dependencies
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False
    print("❌ Backtrader not installed")


def create_sample_data():
    """Create sample OHLCV data for testing"""
    np.random.seed(42)
    
    # Create date range
    start_date = datetime(2025, 6, 1)
    end_date = datetime(2025, 6, 7)
    dates = pd.date_range(start_date, end_date, freq='5T')
    
    # Generate sample price data
    close_prices = []
    current_price = 100.0
    
    for _ in range(len(dates)):
        # Random walk with slight upward bias
        change = np.random.normal(0.001, 0.01)
        current_price *= (1 + change)
        close_prices.append(current_price)
    
    # Generate OHLCV data
    data = []
    for i, (date, close) in enumerate(zip(dates, close_prices)):
        high = close * (1 + abs(np.random.normal(0, 0.005)))
        low = close * (1 - abs(np.random.normal(0, 0.005)))
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


def create_sample_fvg_data():
    """Create sample FVG data for testing"""
    return [
        {
            'id': 1,
            'symbol': 'BTC/USD',
            'upper_bound': 102.5,
            'lower_bound': 101.5,
            'created_at': datetime(2025, 6, 2, 10, 0),
            'direction': 'bullish',
            'timeframe': '5T',
            'is_active': True
        },
        {
            'id': 2,
            'symbol': 'BTC/USD',
            'upper_bound': 104.0,
            'lower_bound': 103.0,
            'created_at': datetime(2025, 6, 3, 14, 30),
            'direction': 'bearish',
            'timeframe': '5T',
            'is_active': True
        }
    ]


class SimpleFVGStrategy(bt.Strategy):
    """Simple FVG-based strategy for testing"""
    
    params = (
        ('risk_per_trade', 0.02),
        ('reward_risk_ratio', 2.0),
        ('debug', True),
    )
    
    def __init__(self):
        # EMA indicators
        self.ema_20 = bt.indicators.EMA(period=20)
        self.ema_50 = bt.indicators.EMA(period=50)
        
        # Sample FVG data
        self.fvg_zones = create_sample_fvg_data()
        
        # Track trades
        self.trades = []
        
    def next(self):
        if not self.position:
            # Look for entry signals
            if self.data.close[0] > self.ema_20[0] > self.ema_50[0]:
                # Check if price is in FVG zone
                for fvg in self.fvg_zones:
                    if (fvg['lower_bound'] <= self.data.close[0] <= fvg['upper_bound'] and
                        fvg['direction'] == 'bullish'):
                        
                        # Calculate position size
                        risk_amount = self.broker.get_value() * self.params.risk_per_trade
                        stop_loss = self.data.close[0] * 0.98  # 2% stop loss
                        position_size = risk_amount / (self.data.close[0] - stop_loss)
                        
                        # Place order
                        self.buy(size=position_size)
                        
                        if self.params.debug:
                            print(f"BUY: Price={self.data.close[0]:.2f}, Size={position_size:.2f}")
                        
                        break
        
        else:
            # Manage existing position
            if self.position.size > 0:  # Long position
                # Take profit at 2:1 ratio
                entry_price = self.position.price
                stop_loss = entry_price * 0.98
                take_profit = entry_price + (entry_price - stop_loss) * self.params.reward_risk_ratio
                
                if self.data.close[0] >= take_profit:
                    self.sell()
                    if self.params.debug:
                        print(f"SELL (TP): Price={self.data.close[0]:.2f}, Profit={self.data.close[0] - entry_price:.2f}")
                elif self.data.close[0] <= stop_loss:
                    self.sell()
                    if self.params.debug:
                        print(f"SELL (SL): Price={self.data.close[0]:.2f}, Loss={self.data.close[0] - entry_price:.2f}")
    
    def notify_trade(self, trade):
        if trade.isclosed:
            self.trades.append({
                'pnl': trade.pnl,
                'pnlcomm': trade.pnlcomm,
                'size': trade.size,
                'price': trade.price,
                'value': trade.value,
                'commission': trade.commission
            })


def test_simple_backtrader_integration():
    """Test simple Backtrader integration"""
    print("🧪 Testing Simple Backtrader Integration")
    print("=" * 50)
    
    if not BACKTRADER_AVAILABLE:
        print("❌ Backtrader not available")
        return False
    
    try:
        # Create cerebro instance
        cerebro = bt.Cerebro()
        
        # Add strategy
        cerebro.addstrategy(SimpleFVGStrategy)
        
        # Create and add data feed
        data_df = create_sample_data()
        data_df.set_index('datetime', inplace=True)
        
        # Convert to backtrader data feed
        data_feed = bt.feeds.PandasData(dataname=data_df)
        cerebro.adddata(data_feed)
        
        # Set initial capital
        cerebro.broker.setcash(50000)
        
        # Set commission
        cerebro.broker.setcommission(commission=0.001)
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        
        print(f"Starting Capital: ${cerebro.broker.getvalue():,.2f}")
        
        # Run backtest
        results = cerebro.run()
        
        # Get results
        strat = results[0]
        final_value = cerebro.broker.getvalue()
        
        print(f"Final Capital: ${final_value:,.2f}")
        print(f"Total Return: {((final_value - 50000) / 50000) * 100:.2f}%")
        
        # Print analyzer results
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        returns = strat.analyzers.returns.get_analysis()
        
        print(f"\nAnalyzer Results:")
        print(f"Sharpe Ratio: {sharpe.get('sharperatio', 'N/A')}")
        print(f"Max Drawdown: {drawdown.get('max', {}).get('drawdown', 'N/A'):.2f}%")
        print(f"Total Trades: {len(strat.trades)}")
        
        if len(strat.trades) > 0:
            winning_trades = [t for t in strat.trades if t['pnl'] > 0]
            losing_trades = [t for t in strat.trades if t['pnl'] <= 0]
            
            print(f"Winning Trades: {len(winning_trades)}")
            print(f"Losing Trades: {len(losing_trades)}")
            print(f"Win Rate: {(len(winning_trades) / len(strat.trades)) * 100:.1f}%")
            
            if winning_trades:
                avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
                print(f"Average Win: ${avg_win:.2f}")
            
            if losing_trades:
                avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
                print(f"Average Loss: ${avg_loss:.2f}")
        
        print("\n✅ Simple Backtrader integration test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Simple integration test ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backtrader_components():
    """Test individual Backtrader components"""
    print("\n🧪 Testing Backtrader Components")
    print("=" * 50)
    
    if not BACKTRADER_AVAILABLE:
        print("❌ Backtrader not available")
        return False
    
    try:
        # Test data feed creation
        data_df = create_sample_data()
        print(f"✅ Sample data created: {len(data_df)} rows")
        
        # Test FVG data
        fvg_data = create_sample_fvg_data()
        print(f"✅ FVG data created: {len(fvg_data)} zones")
        
        # Test cerebro creation
        cerebro = bt.Cerebro()
        print(f"✅ Cerebro instance created")
        
        # Test strategy addition
        cerebro.addstrategy(SimpleFVGStrategy)
        print(f"✅ Strategy added")
        
        # Test data feed addition
        data_df.set_index('datetime', inplace=True)
        data_feed = bt.feeds.PandasData(dataname=data_df)
        cerebro.adddata(data_feed)
        print(f"✅ Data feed added")
        
        # Test broker settings
        cerebro.broker.setcash(10000)
        cerebro.broker.setcommission(commission=0.001)
        print(f"✅ Broker configured")
        
        # Test analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        print(f"✅ Analyzers added")
        
        print("\n✅ All Backtrader components test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Components test ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_processing():
    """Test data processing capabilities"""
    print("\n🧪 Testing Data Processing")
    print("=" * 50)
    
    try:
        # Create sample data
        data_df = create_sample_data()
        
        # Test data structure
        expected_columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        if all(col in data_df.columns for col in expected_columns):
            print("✅ Data structure correct")
        else:
            print("❌ Data structure incorrect")
            return False
        
        # Test data quality
        if not data_df.isnull().any().any():
            print("✅ No missing values")
        else:
            print("❌ Missing values found")
            return False
        
        # Test data range
        if len(data_df) > 100:
            print(f"✅ Sufficient data: {len(data_df)} rows")
        else:
            print(f"❌ Insufficient data: {len(data_df)} rows")
            return False
        
        # Test FVG data
        fvg_data = create_sample_fvg_data()
        if len(fvg_data) > 0:
            print(f"✅ FVG data available: {len(fvg_data)} zones")
        else:
            print("❌ No FVG data")
            return False
        
        print("\n✅ Data processing test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Data processing test ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    print("🚀 SIMPLE BACKTRADER INTEGRATION TESTS")
    print("=" * 60)
    
    tests = [
        ("Data Processing", test_data_processing),
        ("Backtrader Components", test_backtrader_components),
        ("Simple Integration", test_simple_backtrader_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} ERROR: {e}")
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed / len(tests)) * 100:.1f}%")
    
    if passed == len(tests):
        print(f"\n🎉 ALL TESTS PASSED! Basic Backtrader integration works!")
    elif passed > 0:
        print(f"\n⚠️  {passed}/{len(tests)} tests passed. Basic functionality working.")
    else:
        print(f"\n❌ All tests failed. Need to debug setup.")
    
    return passed, failed


def demonstrate_integration_features():
    """Demonstrate integration features"""
    print("\n🎯 BACKTRADER INTEGRATION FEATURES")
    print("=" * 50)
    
    features = [
        "✅ Professional Backtrader Setup",
        "✅ Custom FVG Strategy Implementation",
        "✅ Sample Data Generation",
        "✅ EMA Trend Filtering",
        "✅ Risk Management (2% per trade)",
        "✅ Reward:Risk Ratio (2:1)",
        "✅ Multiple Analyzers",
        "✅ Trade Tracking",
        "✅ Performance Metrics",
        "✅ Modular Architecture",
        "✅ Error Handling",
        "✅ Debug Capabilities"
    ]
    
    for feature in features:
        print(f"   {feature}")
    
    print(f"\n💡 NEXT STEPS:")
    print(f"   1. Complete database integration")
    print(f"   2. Add real FVG detection")
    print(f"   3. Implement live data feeds")
    print(f"   4. Add portfolio management")
    print(f"   5. Create optimization tools")
    print(f"   6. Add visualization features")


if __name__ == "__main__":
    print("🚀 Starting Simple Backtrader Integration Tests...")
    
    # Run all tests
    passed, failed = run_all_tests()
    
    # Demonstrate features
    demonstrate_integration_features()
    
    # Final message
    print(f"\n{'='*60}")
    print("SIMPLE BACKTRADER INTEGRATION - COMPLETE")
    print(f"{'='*60}")
    
    if passed > failed:
        print("🎉 Basic integration successful!")
        print("🔧 Foundation ready for full integration")
    else:
        print("⚠️  Basic integration needs work")
    
    print(f"\n✅ Simple Backtrader test complete!")
