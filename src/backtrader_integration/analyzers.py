"""
Custom Analyzers for FVG Strategy
Professional analyzers for enhanced performance analysis
"""

import backtrader as bt
import pandas as pd
from typing import Dict, List, Any, Optional
from collections import defaultdict
import numpy as np


class FVGAnalyzer(bt.Analyzer):
    """
    Custom analyzer for FVG-specific metrics
    Tracks FVG zone performance and statistics
    """
    
    def __init__(self):
        self.fvg_zones = []
        self.fvg_touches = defaultdict(int)
        self.fvg_success_rate = defaultdict(list)
        self.timeframe_performance = defaultdict(list)
        self.session_performance = defaultdict(list)
        
    def start(self):
        """Called at start of backtest"""
        self.fvg_zones = []
        self.fvg_touches = defaultdict(int)
        self.fvg_success_rate = defaultdict(list)
        self.timeframe_performance = defaultdict(list)
        self.session_performance = defaultdict(list)
    
    def next(self):
        """Called for each bar"""
        # Track FVG zones and their performance
        # This would be populated by the strategy
        pass
    
    def stop(self):
        """Called at end of backtest"""
        # Calculate final FVG statistics
        pass
    
    def get_analysis(self) -> Dict[str, Any]:
        """
        Return FVG analysis results
        
        Returns:
            Dictionary with FVG-specific metrics
        """
        return {
            'total_fvg_zones': len(self.fvg_zones),
            'fvg_touches': dict(self.fvg_touches),
            'fvg_success_rate': dict(self.fvg_success_rate),
            'timeframe_performance': dict(self.timeframe_performance),
            'session_performance': dict(self.session_performance)
        }


class TradingSessionAnalyzer(bt.Analyzer):
    """
    Analyzer for trading session performance
    Tracks performance by different trading sessions
    """
    
    def __init__(self):
        self.session_trades = {
            'evening': [],      # 20:00-00:00
            'early_morning': [], # 02:00-04:00
            'morning': [],      # 08:00-13:00
            'other': []         # Outside trading hours
        }
        
    def start(self):
        """Called at start of backtest"""
        self.session_trades = {
            'evening': [],
            'early_morning': [],
            'morning': [],
            'other': []
        }
    
    def notify_trade(self, trade):
        """Called when a trade is closed"""
        if trade.isclosed:
            # Get trade entry time
            entry_time = trade.open_datetime()
            hour = entry_time.hour
            
            # Classify by session
            if (20 <= hour <= 23) or (hour == 0):
                session = 'evening'
            elif 2 <= hour <= 3:
                session = 'early_morning'
            elif 8 <= hour <= 12:
                session = 'morning'
            else:
                session = 'other'
            
            # Store trade info
            trade_info = {
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl / abs(trade.value) * 100,
                'entry_time': entry_time,
                'duration': trade.close_datetime() - entry_time
            }
            
            self.session_trades[session].append(trade_info)
    
    def get_analysis(self) -> Dict[str, Any]:
        """
        Return session analysis results
        
        Returns:
            Dictionary with session-specific metrics
        """
        analysis = {}
        
        for session, trades in self.session_trades.items():
            if not trades:
                analysis[session] = {
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_pnl': 0,
                    'total_pnl': 0
                }
                continue
            
            winning_trades = [t for t in trades if t['pnl'] > 0]
            total_trades = len(trades)
            win_rate = len(winning_trades) / total_trades * 100
            avg_pnl = sum(t['pnl'] for t in trades) / total_trades
            total_pnl = sum(t['pnl'] for t in trades)
            
            analysis[session] = {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'total_pnl': total_pnl,
                'winning_trades': len(winning_trades),
                'losing_trades': total_trades - len(winning_trades)
            }
        
        return analysis


class RiskMetricsAnalyzer(bt.Analyzer):
    """
    Advanced risk metrics analyzer
    Calculates sophisticated risk measures
    """
    
    def __init__(self):
        self.portfolio_values = []
        self.returns = []
        self.daily_returns = []
        self.peak_value = 0
        self.drawdown_periods = []
        self.current_drawdown_start = None
        
    def start(self):
        """Called at start of backtest"""
        self.portfolio_values = []
        self.returns = []
        self.daily_returns = []
        self.peak_value = self.strategy.broker.getvalue()
        self.drawdown_periods = []
        self.current_drawdown_start = None
    
    def next(self):
        """Called for each bar"""
        current_value = self.strategy.broker.getvalue()
        self.portfolio_values.append(current_value)
        
        # Calculate returns
        if len(self.portfolio_values) > 1:
            prev_value = self.portfolio_values[-2]
            daily_return = (current_value - prev_value) / prev_value
            self.daily_returns.append(daily_return)
        
        # Track drawdowns
        if current_value > self.peak_value:
            # New peak
            if self.current_drawdown_start is not None:
                # End of drawdown period
                drawdown_duration = len(self.portfolio_values) - self.current_drawdown_start
                self.drawdown_periods.append(drawdown_duration)
                self.current_drawdown_start = None
            
            self.peak_value = current_value
        else:
            # In drawdown
            if self.current_drawdown_start is None:
                self.current_drawdown_start = len(self.portfolio_values)
    
    def get_analysis(self) -> Dict[str, Any]:
        """
        Return risk analysis results
        
        Returns:
            Dictionary with risk metrics
        """
        if not self.daily_returns:
            return {}
        
        returns_array = np.array(self.daily_returns)
        
        # Basic risk metrics
        volatility = np.std(returns_array) * np.sqrt(252)  # Annualized
        avg_return = np.mean(returns_array) * 252  # Annualized
        
        # Sharpe ratio (assuming 0% risk-free rate)
        sharpe = avg_return / volatility if volatility > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns_array[returns_array < 0]
        downside_deviation = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino = avg_return / downside_deviation if downside_deviation > 0 else 0
        
        # Value at Risk (VaR) - 5% confidence level
        var_5 = np.percentile(returns_array, 5) if len(returns_array) > 0 else 0
        
        # Conditional VaR (Expected Shortfall)
        cvar_5 = np.mean(returns_array[returns_array <= var_5]) if len(returns_array) > 0 else 0
        
        # Maximum drawdown duration
        max_drawdown_duration = max(self.drawdown_periods) if self.drawdown_periods else 0
        avg_drawdown_duration = np.mean(self.drawdown_periods) if self.drawdown_periods else 0
        
        return {
            'volatility': volatility,
            'avg_return': avg_return,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'var_5': var_5,
            'cvar_5': cvar_5,
            'max_drawdown_duration': max_drawdown_duration,
            'avg_drawdown_duration': avg_drawdown_duration,
            'total_drawdown_periods': len(self.drawdown_periods)
        }


class PerformanceBreakdownAnalyzer(bt.Analyzer):
    """
    Detailed performance breakdown analyzer
    Analyzes performance by various dimensions
    """
    
    def __init__(self):
        self.monthly_returns = defaultdict(list)
        self.weekly_returns = defaultdict(list)
        self.hourly_performance = defaultdict(list)
        self.direction_performance = {'long': [], 'short': []}
        self.fvg_timeframe_performance = defaultdict(list)
        
    def start(self):
        """Called at start of backtest"""
        self.monthly_returns = defaultdict(list)
        self.weekly_returns = defaultdict(list)
        self.hourly_performance = defaultdict(list)
        self.direction_performance = {'long': [], 'short': []}
        self.fvg_timeframe_performance = defaultdict(list)
    
    def notify_trade(self, trade):
        """Called when a trade is closed"""
        if trade.isclosed:
            entry_time = trade.open_datetime()
            pnl = trade.pnl
            pnl_pct = trade.pnl / abs(trade.value) * 100
            
            # Monthly breakdown
            month_key = entry_time.strftime("%Y-%m")
            self.monthly_returns[month_key].append(pnl)
            
            # Weekly breakdown
            week_key = entry_time.strftime("%Y-W%U")
            self.weekly_returns[week_key].append(pnl)
            
            # Hourly breakdown
            hour_key = entry_time.hour
            self.hourly_performance[hour_key].append(pnl)
            
            # Direction breakdown (would need to be passed from strategy)
            # This is simplified - in real implementation, strategy would provide this info
            
    def get_analysis(self) -> Dict[str, Any]:
        """
        Return performance breakdown results
        
        Returns:
            Dictionary with breakdown metrics
        """
        analysis = {}
        
        # Monthly performance
        monthly_analysis = {}
        for month, returns in self.monthly_returns.items():
            monthly_analysis[month] = {
                'total_pnl': sum(returns),
                'avg_pnl': np.mean(returns),
                'trades_count': len(returns),
                'win_rate': len([r for r in returns if r > 0]) / len(returns) * 100
            }
        analysis['monthly'] = monthly_analysis
        
        # Weekly performance
        weekly_analysis = {}
        for week, returns in self.weekly_returns.items():
            weekly_analysis[week] = {
                'total_pnl': sum(returns),
                'avg_pnl': np.mean(returns),
                'trades_count': len(returns)
            }
        analysis['weekly'] = weekly_analysis
        
        # Hourly performance
        hourly_analysis = {}
        for hour, returns in self.hourly_performance.items():
            hourly_analysis[hour] = {
                'total_pnl': sum(returns),
                'avg_pnl': np.mean(returns),
                'trades_count': len(returns),
                'win_rate': len([r for r in returns if r > 0]) / len(returns) * 100
            }
        analysis['hourly'] = hourly_analysis
        
        return analysis


class ConsistencyAnalyzer(bt.Analyzer):
    """
    Consistency analyzer for strategy performance
    Measures consistency across different time periods
    """
    
    def __init__(self):
        self.daily_pnl = defaultdict(float)
        self.weekly_pnl = defaultdict(float)
        self.monthly_pnl = defaultdict(float)
        self.current_day = None
        self.current_week = None
        self.current_month = None
        
    def start(self):
        """Called at start of backtest"""
        self.daily_pnl = defaultdict(float)
        self.weekly_pnl = defaultdict(float)
        self.monthly_pnl = defaultdict(float)
        self.current_day = None
        self.current_week = None
        self.current_month = None
    
    def notify_trade(self, trade):
        """Called when a trade is closed"""
        if trade.isclosed:
            entry_time = trade.open_datetime()
            pnl = trade.pnl
            
            # Daily aggregation
            day_key = entry_time.strftime("%Y-%m-%d")
            self.daily_pnl[day_key] += pnl
            
            # Weekly aggregation
            week_key = entry_time.strftime("%Y-W%U")
            self.weekly_pnl[week_key] += pnl
            
            # Monthly aggregation
            month_key = entry_time.strftime("%Y-%m")
            self.monthly_pnl[month_key] += pnl
    
    def get_analysis(self) -> Dict[str, Any]:
        """
        Return consistency analysis results
        
        Returns:
            Dictionary with consistency metrics
        """
        analysis = {}
        
        # Daily consistency
        daily_returns = list(self.daily_pnl.values())
        if daily_returns:
            profitable_days = len([r for r in daily_returns if r > 0])
            total_days = len(daily_returns)
            
            analysis['daily'] = {
                'profitable_days': profitable_days,
                'total_days': total_days,
                'profitable_day_ratio': profitable_days / total_days * 100,
                'avg_daily_pnl': np.mean(daily_returns),
                'std_daily_pnl': np.std(daily_returns),
                'best_day': max(daily_returns),
                'worst_day': min(daily_returns)
            }
        
        # Weekly consistency
        weekly_returns = list(self.weekly_pnl.values())
        if weekly_returns:
            profitable_weeks = len([r for r in weekly_returns if r > 0])
            total_weeks = len(weekly_returns)
            
            analysis['weekly'] = {
                'profitable_weeks': profitable_weeks,
                'total_weeks': total_weeks,
                'profitable_week_ratio': profitable_weeks / total_weeks * 100,
                'avg_weekly_pnl': np.mean(weekly_returns),
                'std_weekly_pnl': np.std(weekly_returns),
                'best_week': max(weekly_returns),
                'worst_week': min(weekly_returns)
            }
        
        # Monthly consistency
        monthly_returns = list(self.monthly_pnl.values())
        if monthly_returns:
            profitable_months = len([r for r in monthly_returns if r > 0])
            total_months = len(monthly_returns)
            
            analysis['monthly'] = {
                'profitable_months': profitable_months,
                'total_months': total_months,
                'profitable_month_ratio': profitable_months / total_months * 100,
                'avg_monthly_pnl': np.mean(monthly_returns),
                'std_monthly_pnl': np.std(monthly_returns),
                'best_month': max(monthly_returns),
                'worst_month': min(monthly_returns)
            }
        
        return analysis


if __name__ == "__main__":
    # Test analyzers
    print("🧪 Testing Custom Analyzers...")
    
    print("✅ Analyzers defined successfully!")
    print("   - FVGAnalyzer: FVG-specific metrics")
    print("   - TradingSessionAnalyzer: Session performance")
    print("   - RiskMetricsAnalyzer: Advanced risk metrics")
    print("   - PerformanceBreakdownAnalyzer: Detailed breakdown")
    print("   - ConsistencyAnalyzer: Consistency metrics")
