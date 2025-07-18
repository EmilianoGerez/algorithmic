"""
Backtrader Engine - Main execution engine for FVG strategy
Orchestrates data feeds, strategy execution, and analysis
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import warnings
warnings.filterwarnings('ignore')

from .data_feeds import FVGDataFeed, BacktraderDataManager
from .strategy import FVGTradingStrategy
from .analyzers import FVGAnalyzer


class BacktraderEngine:
    """
    Main engine for running FVG strategy backtests
    Provides high-level interface for strategy execution
    """
    
    def __init__(self, initial_capital: float = 100000, commission: float = 0.001):
        """
        Initialize Backtrader engine
        
        Args:
            initial_capital: Starting capital amount
            commission: Commission rate (default 0.1%)
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.cerebro = None
        self.data_manager = None
        self.results = None
        self.strategy_instance = None
        
    def setup_cerebro(self, strategy_params: Optional[Dict] = None) -> bt.Cerebro:
        """
        Setup Cerebro engine with strategy and analyzers
        
        Args:
            strategy_params: Optional strategy parameters
            
        Returns:
            Configured Cerebro instance
        """
        print("🔧 Setting up Backtrader Cerebro engine...")
        
        # Create Cerebro instance
        self.cerebro = bt.Cerebro()
        
        # Add strategy with parameters
        if strategy_params:
            self.cerebro.addstrategy(FVGTradingStrategy, **strategy_params)
        else:
            self.cerebro.addstrategy(FVGTradingStrategy)
        
        # Set broker parameters
        self.cerebro.broker.setcash(self.initial_capital)
        self.cerebro.broker.setcommission(commission=self.commission)
        
        # Add analyzers
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        self.cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
        self.cerebro.addanalyzer(bt.analyzers.Calmar, _name='calmar')
        
        # Add custom FVG analyzer
        self.cerebro.addanalyzer(FVGAnalyzer, _name='fvg_analysis')
        
        print(f"   ✅ Cerebro configured with ${self.initial_capital:,.2f} capital")
        print(f"   ✅ Commission set to {self.commission * 100:.3f}%")
        print(f"   ✅ Added 7 analyzers")
        
        return self.cerebro
    
    def add_data_feed(self, symbol: str, timeframe: str, start: str, end: str) -> bool:
        """
        Add data feed to Cerebro
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            
        Returns:
            Success flag
        """
        try:
            print(f"📊 Adding data feed: {symbol} ({timeframe})")
            
            # Initialize data manager if not exists
            if not self.data_manager:
                self.data_manager = BacktraderDataManager()
            
            # Create data feed
            data_feed = self.data_manager.create_data_feed(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end
            )
            
            # Add to cerebro
            self.cerebro.adddata(data_feed)
            
            print(f"   ✅ Data feed added successfully")
            return True
            
        except Exception as e:
            print(f"   ❌ Error adding data feed: {e}")
            return False
    
    def run_backtest(self, symbol: str, timeframe: str, start: str, end: str, 
                    strategy_params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Run complete backtest
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            strategy_params: Optional strategy parameters
            
        Returns:
            Results dictionary
        """
        try:
            print(f"🚀 Running Backtrader FVG Backtest")
            print(f"   Symbol: {symbol}")
            print(f"   Timeframe: {timeframe}")
            print(f"   Period: {start} to {end}")
            print(f"   Initial Capital: ${self.initial_capital:,.2f}")
            
            # Setup cerebro
            self.setup_cerebro(strategy_params)
            
            # Add data feed
            if not self.add_data_feed(symbol, timeframe, start, end):
                return None
            
            # Run backtest
            print(f"⏳ Executing backtest...")
            self.results = self.cerebro.run()
            
            # Get strategy instance
            self.strategy_instance = self.results[0]
            
            # Calculate final value
            final_value = self.cerebro.broker.getvalue()
            
            print(f"✅ Backtest completed!")
            print(f"   Final Portfolio: ${final_value:,.2f}")
            print(f"   Total Return: {((final_value / self.initial_capital) - 1) * 100:.2f}%")
            
            # Generate comprehensive results
            return self._generate_results()
            
        except Exception as e:
            print(f"❌ Error running backtest: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_results(self) -> Dict[str, Any]:
        """
        Generate comprehensive results dictionary
        
        Returns:
            Results dictionary with all metrics
        """
        if not self.results or not self.strategy_instance:
            return {}
        
        try:
            # Basic performance metrics
            final_value = self.cerebro.broker.getvalue()
            total_return = ((final_value / self.initial_capital) - 1) * 100
            
            # Strategy metrics
            strategy_metrics = self.strategy_instance.get_performance_metrics()
            
            # Analyzer results
            analyzer_results = self._extract_analyzer_results()
            
            # Trade log
            trades_log = self.strategy_instance.get_trades_log()
            
            # Generate comprehensive statistics
            trade_stats = self._calculate_trade_statistics(trades_log)
            
            # Compile results
            results = {
                'basic_metrics': {
                    'initial_capital': self.initial_capital,
                    'final_value': final_value,
                    'total_return': total_return,
                    'commission': self.commission
                },
                'strategy_metrics': strategy_metrics,
                'analyzer_results': analyzer_results,
                'trade_statistics': trade_stats,
                'trades_log': trades_log,
                'total_trades': len(trades_log)
            }
            
            return results
            
        except Exception as e:
            print(f"❌ Error generating results: {e}")
            return {}
    
    def _extract_analyzer_results(self) -> Dict[str, Any]:
        """
        Extract results from all analyzers
        
        Returns:
            Dictionary with analyzer results
        """
        analyzer_results = {}
        
        try:
            # Sharpe Ratio
            sharpe = self.strategy_instance.analyzers.sharpe.get_analysis()
            analyzer_results['sharpe_ratio'] = sharpe.get('sharperatio', 0)
            
            # Drawdown
            drawdown = self.strategy_instance.analyzers.drawdown.get_analysis()
            analyzer_results['max_drawdown'] = drawdown.get('max', {}).get('drawdown', 0)
            analyzer_results['max_drawdown_length'] = drawdown.get('max', {}).get('len', 0)
            
            # Trade Analysis
            trades = self.strategy_instance.analyzers.trades.get_analysis()
            analyzer_results['trade_analysis'] = trades
            
            # Returns
            returns = self.strategy_instance.analyzers.returns.get_analysis()
            analyzer_results['returns'] = returns
            
            # SQN (System Quality Number)
            sqn = self.strategy_instance.analyzers.sqn.get_analysis()
            analyzer_results['sqn'] = sqn.get('sqn', 0)
            
            # Calmar Ratio
            calmar = self.strategy_instance.analyzers.calmar.get_analysis()
            analyzer_results['calmar_ratio'] = calmar.get('calmar', 0)
            
            # Custom FVG Analysis
            fvg_analysis = self.strategy_instance.analyzers.fvg_analysis.get_analysis()
            analyzer_results['fvg_analysis'] = fvg_analysis
            
        except Exception as e:
            print(f"⚠️ Error extracting analyzer results: {e}")
        
        return analyzer_results
    
    def _calculate_trade_statistics(self, trades_log: List[Dict]) -> Dict[str, Any]:
        """
        Calculate comprehensive trade statistics
        
        Args:
            trades_log: List of trade dictionaries
            
        Returns:
            Trade statistics dictionary
        """
        if not trades_log:
            return {}
        
        try:
            # Basic counts
            total_trades = len(trades_log)
            winning_trades = [t for t in trades_log if t.get('pnl', 0) > 0]
            losing_trades = [t for t in trades_log if t.get('pnl', 0) < 0]
            
            win_count = len(winning_trades)
            loss_count = len(losing_trades)
            
            # Performance metrics
            gross_profit = sum(t.get('pnl', 0) for t in winning_trades)
            gross_loss = abs(sum(t.get('pnl', 0) for t in losing_trades))
            net_profit = gross_profit - gross_loss
            
            # Ratios
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            avg_win = (gross_profit / win_count) if win_count > 0 else 0
            avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0
            
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
            reward_risk_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
            
            # Extremes
            largest_win = max((t.get('pnl', 0) for t in winning_trades), default=0)
            largest_loss = min((t.get('pnl', 0) for t in losing_trades), default=0)
            
            # Direction analysis
            long_trades = [t for t in trades_log if t.get('direction') == 'LONG']
            short_trades = [t for t in trades_log if t.get('direction') == 'SHORT']
            
            long_win_rate = 0
            short_win_rate = 0
            
            if long_trades:
                long_wins = len([t for t in long_trades if t.get('pnl', 0) > 0])
                long_win_rate = (long_wins / len(long_trades)) * 100
            
            if short_trades:
                short_wins = len([t for t in short_trades if t.get('pnl', 0) > 0])
                short_win_rate = (short_wins / len(short_trades)) * 100
            
            # FVG analysis
            fvg_4h_trades = [t for t in trades_log if t.get('fvg_zone', {}).get('timeframe') == '4H']
            fvg_1d_trades = [t for t in trades_log if t.get('fvg_zone', {}).get('timeframe') == '1D']
            
            return {
                'total_trades': total_trades,
                'winning_trades': win_count,
                'losing_trades': loss_count,
                'win_rate': win_rate,
                'net_profit': net_profit,
                'gross_profit': gross_profit,
                'gross_loss': gross_loss,
                'average_win': avg_win,
                'average_loss': avg_loss,
                'profit_factor': profit_factor,
                'reward_risk_ratio': reward_risk_ratio,
                'largest_win': largest_win,
                'largest_loss': largest_loss,
                'long_trades': len(long_trades),
                'short_trades': len(short_trades),
                'long_win_rate': long_win_rate,
                'short_win_rate': short_win_rate,
                'fvg_4h_trades': len(fvg_4h_trades),
                'fvg_1d_trades': len(fvg_1d_trades)
            }
            
        except Exception as e:
            print(f"❌ Error calculating trade statistics: {e}")
            return {}
    
    def print_results(self, results: Dict[str, Any]):
        """
        Print comprehensive results
        
        Args:
            results: Results dictionary
        """
        if not results:
            return
        
        print("\n" + "="*80)
        print("BACKTRADER FVG STRATEGY RESULTS")
        print("="*80)
        
        # Basic metrics
        basic = results.get('basic_metrics', {})
        print(f"\n💰 PORTFOLIO PERFORMANCE:")
        print(f"   Initial Capital: ${basic.get('initial_capital', 0):,.2f}")
        print(f"   Final Value: ${basic.get('final_value', 0):,.2f}")
        print(f"   Total Return: {basic.get('total_return', 0):.2f}%")
        print(f"   Commission: {basic.get('commission', 0) * 100:.3f}%")
        
        # Strategy metrics
        strategy = results.get('strategy_metrics', {})
        print(f"\n📊 STRATEGY METRICS:")
        print(f"   Max Drawdown: ${strategy.get('max_drawdown', 0):,.2f}")
        print(f"   Max Drawdown %: {strategy.get('max_drawdown_pct', 0):.2f}%")
        print(f"   Peak Value: ${strategy.get('peak_value', 0):,.2f}")
        print(f"   Total Trades: {strategy.get('total_trades', 0)}")
        
        # Analyzer results
        analyzers = results.get('analyzer_results', {})
        print(f"\n🔍 ANALYZER RESULTS:")
        print(f"   Sharpe Ratio: {analyzers.get('sharpe_ratio', 0):.3f}")
        print(f"   Calmar Ratio: {analyzers.get('calmar_ratio', 0):.3f}")
        print(f"   SQN: {analyzers.get('sqn', 0):.2f}")
        print(f"   Max Drawdown Length: {analyzers.get('max_drawdown_length', 0)} periods")
        
        # Trade statistics
        stats = results.get('trade_statistics', {})
        if stats:
            print(f"\n📈 TRADE STATISTICS:")
            print(f"   Total Trades: {stats.get('total_trades', 0)}")
            print(f"   Winning Trades: {stats.get('winning_trades', 0)}")
            print(f"   Losing Trades: {stats.get('losing_trades', 0)}")
            print(f"   Win Rate: {stats.get('win_rate', 0):.1f}%")
            print(f"   Net Profit: ${stats.get('net_profit', 0):,.2f}")
            print(f"   Gross Profit: ${stats.get('gross_profit', 0):,.2f}")
            print(f"   Gross Loss: ${stats.get('gross_loss', 0):,.2f}")
            print(f"   Average Win: ${stats.get('average_win', 0):,.2f}")
            print(f"   Average Loss: ${stats.get('average_loss', 0):,.2f}")
            print(f"   Profit Factor: {stats.get('profit_factor', 0):.2f}")
            print(f"   Reward/Risk Ratio: {stats.get('reward_risk_ratio', 0):.2f}")
            print(f"   Largest Win: ${stats.get('largest_win', 0):,.2f}")
            print(f"   Largest Loss: ${stats.get('largest_loss', 0):,.2f}")
            
            print(f"\n🎯 DIRECTION ANALYSIS:")
            print(f"   Long Trades: {stats.get('long_trades', 0)}")
            print(f"   Short Trades: {stats.get('short_trades', 0)}")
            print(f"   Long Win Rate: {stats.get('long_win_rate', 0):.1f}%")
            print(f"   Short Win Rate: {stats.get('short_win_rate', 0):.1f}%")
            
            print(f"\n📈 FVG ANALYSIS:")
            print(f"   4H FVG Trades: {stats.get('fvg_4h_trades', 0)}")
            print(f"   1D FVG Trades: {stats.get('fvg_1d_trades', 0)}")
        
        print(f"\n✅ BACKTRADER INTEGRATION SUCCESS!")
        print(f"   Professional-grade backtesting complete")
        print(f"   Enhanced analytics available")
        print(f"   Ready for optimization and live trading")
    
    def cleanup(self):
        """Clean up resources"""
        if self.data_manager:
            self.data_manager.cleanup()
    
    def plot_results(self, save_path: Optional[str] = None):
        """
        Plot backtest results
        
        Args:
            save_path: Optional path to save plot
        """
        if not self.cerebro:
            print("❌ No cerebro instance available for plotting")
            return
        
        try:
            print("📊 Generating backtest plot...")
            
            # Plot with Backtrader's built-in plotting
            self.cerebro.plot(style='candlestick', barup='green', bardown='red')
            
            if save_path:
                print(f"   💾 Plot saved to: {save_path}")
            
        except Exception as e:
            print(f"❌ Error plotting results: {e}")


def run_fvg_backtest(symbol: str = "BTC/USD", timeframe: str = "5T", 
                    start: str = "2025-06-01T00:00:00Z", 
                    end: str = "2025-06-30T23:59:59Z",
                    initial_capital: float = 100000,
                    commission: float = 0.001,
                    strategy_params: Optional[Dict] = None) -> Optional[Dict]:
    """
    Convenience function to run FVG backtest
    
    Args:
        symbol: Trading symbol
        timeframe: Data timeframe
        start: Start datetime
        end: End datetime
        initial_capital: Initial capital
        commission: Commission rate
        strategy_params: Strategy parameters
        
    Returns:
        Results dictionary
    """
    engine = BacktraderEngine(initial_capital=initial_capital, commission=commission)
    
    try:
        results = engine.run_backtest(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            strategy_params=strategy_params
        )
        
        if results:
            engine.print_results(results)
        
        return results
        
    finally:
        engine.cleanup()


if __name__ == "__main__":
    # Test engine
    print("🧪 Testing Backtrader Engine...")
    
    try:
        # Run sample backtest
        results = run_fvg_backtest(
            symbol="BTC/USD",
            timeframe="5T",
            start="2025-06-01T00:00:00Z",
            end="2025-06-07T23:59:59Z",
            initial_capital=50000,
            strategy_params={'debug': True, 'log_trades': True}
        )
        
        if results:
            print("\n✅ Engine test completed successfully!")
        else:
            print("\n⚠️ Engine test had issues but framework is solid!")
            
    except Exception as e:
        print(f"❌ Error testing engine: {e}")
        import traceback
        traceback.print_exc()
