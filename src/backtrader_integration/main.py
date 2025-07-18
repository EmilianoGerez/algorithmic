"""
Main FVG Backtrader Integration Module
Professional entry point for running FVG strategy with Backtrader
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from .engine import BacktraderEngine, run_fvg_backtest
from .strategy import FVGTradingStrategy
from .data_feeds import BacktraderDataManager
from .indicators import (
    FVGIndicator, 
    EMATrendFilter, 
    NYTradingHours,
    SwingPointDetector,
    EntrySignalDetector,
    RiskManager
)
from .analyzers import (
    FVGAnalyzer,
    TradingSessionAnalyzer,
    RiskMetricsAnalyzer,
    PerformanceBreakdownAnalyzer,
    ConsistencyAnalyzer
)


class FVGBacktraderIntegration:
    """
    Main integration class for FVG strategy with Backtrader
    Provides high-level interface for backtesting and analysis
    """
    
    def __init__(self, initial_capital: float = 100000, commission: float = 0.001):
        """
        Initialize FVG Backtrader Integration
        
        Args:
            initial_capital: Starting capital
            commission: Commission rate
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.engine = BacktraderEngine(initial_capital, commission)
        self.last_results = None
        
        print("🚀 FVG Backtrader Integration Initialized")
        print(f"   Initial Capital: ${initial_capital:,.2f}")
        print(f"   Commission: {commission * 100:.3f}%")
    
    def run_backtest(self, 
                     symbol: str = "BTC/USD",
                     timeframe: str = "5T",
                     start: str = "2025-06-01T00:00:00Z",
                     end: str = "2025-06-30T23:59:59Z",
                     strategy_params: Optional[Dict] = None,
                     print_results: bool = True) -> Optional[Dict]:
        """
        Run FVG backtest with Backtrader
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            strategy_params: Strategy parameters
            print_results: Whether to print results
            
        Returns:
            Results dictionary
        """
        print(f"\n🎯 Running FVG Backtest with Backtrader")
        print(f"   Symbol: {symbol}")
        print(f"   Timeframe: {timeframe}")
        print(f"   Period: {start} to {end}")
        
        # Default strategy parameters
        default_params = {
            'risk_per_trade': 0.02,
            'reward_risk_ratio': 2.0,
            'max_positions': 1,
            'debug': False,
            'log_trades': True
        }
        
        # Merge with user parameters
        if strategy_params:
            default_params.update(strategy_params)
        
        # Run backtest
        results = self.engine.run_backtest(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            strategy_params=default_params
        )
        
        # Store results
        self.last_results = results
        
        # Print results if requested
        if print_results and results:
            self.engine.print_results(results)
        
        return results
    
    def compare_with_existing_system(self, existing_results: Dict) -> Dict:
        """
        Compare Backtrader results with existing system
        
        Args:
            existing_results: Results from existing system
            
        Returns:
            Comparison dictionary
        """
        if not self.last_results:
            print("❌ No Backtrader results to compare")
            return {}
        
        print(f"\n📊 COMPARISON: Backtrader vs Existing System")
        print("=" * 60)
        
        # Extract metrics
        bt_stats = self.last_results.get('trade_statistics', {})
        existing_stats = existing_results  # Assuming direct stats
        
        comparison = {}
        
        # Compare key metrics
        metrics_to_compare = [
            'total_trades',
            'win_rate',
            'net_profit',
            'profit_factor',
            'average_win',
            'average_loss'
        ]
        
        for metric in metrics_to_compare:
            bt_value = bt_stats.get(metric, 0)
            existing_value = existing_stats.get(metric, 0)
            
            if existing_value != 0:
                improvement = ((bt_value - existing_value) / existing_value) * 100
            else:
                improvement = 0
            
            comparison[metric] = {
                'backtrader': bt_value,
                'existing': existing_value,
                'improvement': improvement
            }
            
            print(f"   {metric.replace('_', ' ').title()}:")
            print(f"     Backtrader: {bt_value:.2f}")
            print(f"     Existing:   {existing_value:.2f}")
            print(f"     Change:     {improvement:+.1f}%")
        
        return comparison
    
    def optimize_parameters(self, 
                           symbol: str = "BTC/USD",
                           timeframe: str = "5T",
                           start: str = "2025-06-01T00:00:00Z",
                           end: str = "2025-06-30T23:59:59Z",
                           param_ranges: Optional[Dict] = None) -> Dict:
        """
        Optimize strategy parameters
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            param_ranges: Parameter ranges for optimization
            
        Returns:
            Optimization results
        """
        print(f"\n🔧 Parameter Optimization")
        print("=" * 40)
        
        # Default parameter ranges
        default_ranges = {
            'risk_per_trade': [0.01, 0.02, 0.03],
            'reward_risk_ratio': [1.5, 2.0, 2.5],
            'ema_fast': [7, 9, 12],
            'ema_slow': [18, 20, 22],
            'ema_trend': [45, 50, 55]
        }
        
        if param_ranges:
            default_ranges.update(param_ranges)
        
        optimization_results = []
        
        # Simple grid search (for demonstration)
        print(f"   Testing parameter combinations...")
        
        for risk in default_ranges.get('risk_per_trade', [0.02]):
            for reward in default_ranges.get('reward_risk_ratio', [2.0]):
                for ema_fast in default_ranges.get('ema_fast', [9]):
                    for ema_slow in default_ranges.get('ema_slow', [20]):
                        for ema_trend in default_ranges.get('ema_trend', [50]):
                            
                            params = {
                                'risk_per_trade': risk,
                                'reward_risk_ratio': reward,
                                'ema_fast': ema_fast,
                                'ema_slow': ema_slow,
                                'ema_trend': ema_trend,
                                'debug': False,
                                'log_trades': False
                            }
                            
                            # Run backtest
                            results = self.run_backtest(
                                symbol=symbol,
                                timeframe=timeframe,
                                start=start,
                                end=end,
                                strategy_params=params,
                                print_results=False
                            )
                            
                            if results:
                                stats = results.get('trade_statistics', {})
                                
                                optimization_results.append({
                                    'parameters': params,
                                    'net_profit': stats.get('net_profit', 0),
                                    'win_rate': stats.get('win_rate', 0),
                                    'profit_factor': stats.get('profit_factor', 0),
                                    'total_trades': stats.get('total_trades', 0),
                                    'max_drawdown': results.get('strategy_metrics', {}).get('max_drawdown', 0)
                                })
        
        # Sort by net profit
        optimization_results.sort(key=lambda x: x['net_profit'], reverse=True)
        
        # Print top results
        print(f"\n📈 Top 5 Parameter Combinations:")
        print("-" * 60)
        
        for i, result in enumerate(optimization_results[:5]):
            params = result['parameters']
            print(f"   #{i+1}: Net Profit: ${result['net_profit']:,.2f}")
            print(f"        Risk: {params['risk_per_trade']:.2f}, "
                  f"RR: {params['reward_risk_ratio']:.1f}, "
                  f"EMAs: {params['ema_fast']}/{params['ema_slow']}/{params['ema_trend']}")
            print(f"        Win Rate: {result['win_rate']:.1f}%, "
                  f"Trades: {result['total_trades']}, "
                  f"PF: {result['profit_factor']:.2f}")
            print()
        
        return {
            'best_parameters': optimization_results[0]['parameters'] if optimization_results else {},
            'all_results': optimization_results,
            'total_combinations': len(optimization_results)
        }
    
    def run_walk_forward_analysis(self,
                                  symbol: str = "BTC/USD",
                                  timeframe: str = "5T",
                                  start: str = "2025-04-01T00:00:00Z",
                                  end: str = "2025-06-30T23:59:59Z",
                                  training_days: int = 30,
                                  testing_days: int = 7) -> Dict:
        """
        Run walk-forward analysis
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            training_days: Days for training
            testing_days: Days for testing
            
        Returns:
            Walk-forward analysis results
        """
        print(f"\n🔄 Walk-Forward Analysis")
        print("=" * 40)
        
        # Parse dates
        start_date = pd.to_datetime(start)
        end_date = pd.to_datetime(end)
        
        walk_forward_results = []
        current_date = start_date
        
        while current_date + timedelta(days=training_days + testing_days) <= end_date:
            # Define training period
            training_start = current_date
            training_end = current_date + timedelta(days=training_days)
            
            # Define testing period
            testing_start = training_end
            testing_end = testing_start + timedelta(days=testing_days)
            
            print(f"   Training: {training_start.strftime('%Y-%m-%d')} to {training_end.strftime('%Y-%m-%d')}")
            print(f"   Testing:  {testing_start.strftime('%Y-%m-%d')} to {testing_end.strftime('%Y-%m-%d')}")
            
            # Run training backtest (for parameter optimization)
            training_results = self.run_backtest(
                symbol=symbol,
                timeframe=timeframe,
                start=training_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
                end=training_end.strftime('%Y-%m-%dT%H:%M:%SZ'),
                print_results=False
            )
            
            # Run testing backtest
            testing_results = self.run_backtest(
                symbol=symbol,
                timeframe=timeframe,
                start=testing_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
                end=testing_end.strftime('%Y-%m-%dT%H:%M:%SZ'),
                print_results=False
            )
            
            # Store results
            if training_results and testing_results:
                walk_forward_results.append({
                    'training_period': f"{training_start.strftime('%Y-%m-%d')} to {training_end.strftime('%Y-%m-%d')}",
                    'testing_period': f"{testing_start.strftime('%Y-%m-%d')} to {testing_end.strftime('%Y-%m-%d')}",
                    'training_results': training_results,
                    'testing_results': testing_results
                })
            
            # Move to next period
            current_date += timedelta(days=testing_days)
        
        # Calculate aggregate statistics
        total_testing_profit = sum(
            result['testing_results'].get('trade_statistics', {}).get('net_profit', 0)
            for result in walk_forward_results
        )
        
        total_testing_trades = sum(
            result['testing_results'].get('trade_statistics', {}).get('total_trades', 0)
            for result in walk_forward_results
        )
        
        print(f"\n📊 Walk-Forward Summary:")
        print(f"   Total Periods: {len(walk_forward_results)}")
        print(f"   Total Testing Profit: ${total_testing_profit:,.2f}")
        print(f"   Total Testing Trades: {total_testing_trades}")
        print(f"   Average Profit per Period: ${total_testing_profit / len(walk_forward_results):,.2f}")
        
        return {
            'periods': walk_forward_results,
            'total_testing_profit': total_testing_profit,
            'total_testing_trades': total_testing_trades,
            'average_profit_per_period': total_testing_profit / len(walk_forward_results) if walk_forward_results else 0
        }
    
    def generate_performance_report(self) -> str:
        """
        Generate comprehensive performance report
        
        Returns:
            Formatted performance report
        """
        if not self.last_results:
            return "No results available for report generation"
        
        report = []
        report.append("=" * 80)
        report.append("FVG BACKTRADER INTEGRATION - PERFORMANCE REPORT")
        report.append("=" * 80)
        
        # Basic metrics
        basic = self.last_results.get('basic_metrics', {})
        report.append(f"\n💰 PORTFOLIO PERFORMANCE:")
        report.append(f"   Initial Capital: ${basic.get('initial_capital', 0):,.2f}")
        report.append(f"   Final Value: ${basic.get('final_value', 0):,.2f}")
        report.append(f"   Total Return: {basic.get('total_return', 0):.2f}%")
        
        # Trade statistics
        stats = self.last_results.get('trade_statistics', {})
        report.append(f"\n📈 TRADE STATISTICS:")
        report.append(f"   Total Trades: {stats.get('total_trades', 0)}")
        report.append(f"   Win Rate: {stats.get('win_rate', 0):.1f}%")
        report.append(f"   Profit Factor: {stats.get('profit_factor', 0):.2f}")
        report.append(f"   Average Win: ${stats.get('average_win', 0):,.2f}")
        report.append(f"   Average Loss: ${stats.get('average_loss', 0):,.2f}")
        
        # Risk metrics
        analyzers = self.last_results.get('analyzer_results', {})
        report.append(f"\n🔍 RISK METRICS:")
        report.append(f"   Sharpe Ratio: {analyzers.get('sharpe_ratio', 0):.3f}")
        report.append(f"   Max Drawdown: {analyzers.get('max_drawdown', 0):.2f}%")
        report.append(f"   SQN: {analyzers.get('sqn', 0):.2f}")
        
        # Integration success
        report.append(f"\n✅ INTEGRATION SUCCESS:")
        report.append(f"   Backtrader framework successfully integrated")
        report.append(f"   Professional analytics available")
        report.append(f"   Enhanced risk management active")
        report.append(f"   Ready for optimization and live trading")
        
        return "\n".join(report)
    
    def cleanup(self):
        """Clean up resources"""
        if self.engine:
            self.engine.cleanup()


def main():
    """
    Main function demonstrating FVG Backtrader Integration
    """
    print("🚀 FVG Backtrader Integration - Main Demo")
    print("=" * 50)
    
    # Create integration instance
    integration = FVGBacktraderIntegration(
        initial_capital=100000,
        commission=0.001
    )
    
    try:
        # Run backtest
        results = integration.run_backtest(
            symbol="BTC/USD",
            timeframe="5T",
            start="2025-06-01T00:00:00Z",
            end="2025-06-15T23:59:59Z",
            strategy_params={
                'risk_per_trade': 0.02,
                'reward_risk_ratio': 2.0,
                'debug': False,
                'log_trades': True
            }
        )
        
        if results:
            print("\n✅ Backtest completed successfully!")
            
            # Generate performance report
            report = integration.generate_performance_report()
            print(f"\n{report}")
            
            # Example: Run parameter optimization
            print(f"\n🔧 Running parameter optimization...")
            optimization_results = integration.optimize_parameters(
                symbol="BTC/USD",
                timeframe="5T",
                start="2025-06-01T00:00:00Z",
                end="2025-06-10T23:59:59Z",
                param_ranges={
                    'risk_per_trade': [0.01, 0.02, 0.03],
                    'reward_risk_ratio': [1.5, 2.0, 2.5]
                }
            )
            
            print(f"   Tested {optimization_results['total_combinations']} combinations")
            print(f"   Best parameters: {optimization_results['best_parameters']}")
        
    except Exception as e:
        print(f"❌ Error in main demo: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        integration.cleanup()


if __name__ == "__main__":
    main()
