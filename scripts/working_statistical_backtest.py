#!/usr/bin/env python3
"""
Working Statistical Backtest - Using Service Pattern
Complete statistical metrics with entries table
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


class WorkingStatisticalBacktester:
    """
    Working Statistical Backtest using the service pattern
    """
    
    def __init__(self):
        self.repo = AlpacaCryptoRepository()
        self.redis = get_redis_connection()
        self.db = SessionLocal()
        self.service = SignalDetectionService(self.repo, self.redis, self.db)
        self.initial_capital = 100000
        self.risk_per_trade = 0.02
        self.trades = []
        self.equity_curve = []
        
    def run_backtest(self, symbol: str, start: str, end: str) -> Dict:
        """
        Run comprehensive statistical backtest
        """
        print("🚀 WORKING STATISTICAL BACKTEST")
        print("=" * 70)
        print(f"📅 Period: {start} to {end}")
        print(f"💰 Initial Capital: ${self.initial_capital:,.2f}")
        print(f"🎯 Risk Per Trade: {self.risk_per_trade*100:.1f}%")
        print("=" * 70)
        
        # Get data using service
        try:
            print("📊 Fetching market data...")
            result = self.service.detect_signals(
                symbol=symbol,
                signal_type="fvg",
                timeframe="15Min",
                start=start,
                end=end
            )
            
            candles = result.get("candles", [])
            fvgs = result.get("tracked_fvgs", [])
            
            print(f"   📈 Candles: {len(candles)}")
            print(f"   🎯 FVGs: {len(fvgs)}")
            
            if not candles:
                print("❌ No data retrieved!")
                return self._generate_empty_report()
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Process FVGs and generate signals
            signals = self._process_fvgs_for_signals(df, fvgs)
            print(f"   ✅ Generated {len(signals)} trading signals")
            
            # Execute trades
            self._execute_trades(df, signals)
            print(f"   💼 Executed {len(self.trades)} trades")
            
            # Calculate comprehensive statistics
            return self._calculate_comprehensive_stats()
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return self._generate_empty_report()
    
    def _process_fvgs_for_signals(self, df: pd.DataFrame, fvgs: List[Dict]) -> List[Dict]:
        """
        Process FVGs and generate trading signals
        """
        signals = []
        
        for fvg in fvgs:
            try:
                # Parse FVG timestamp
                fvg_time = pd.to_datetime(fvg['timestamp'], utc=True)
                zone = fvg['zone']
                direction = fvg['direction']
                
                # Find candles after FVG formation
                future_candles = df[df['timestamp'] > fvg_time].copy()
                
                if len(future_candles) < 10:  # Need at least 10 candles for signal
                    continue
                
                # Look for FVG retest and signal
                for i, candle in future_candles.iterrows():
                    if self._is_fvg_retest(candle, zone, direction):
                        # Found retest - generate signal
                        signal = self._generate_trade_signal(candle, zone, direction, fvg_time)
                        if signal:
                            signals.append(signal)
                            break  # Only one signal per FVG
                        
            except Exception as e:
                continue
        
        return signals
    
    def _is_fvg_retest(self, candle: Dict, zone: List[float], direction: str) -> bool:
        """
        Check if candle represents FVG retest
        """
        zone_low, zone_high = zone
        
        if direction == 'bullish':
            # Bullish FVG - look for price touching zone from above
            return candle['low'] <= zone_high and candle['close'] > zone_low
        else:
            # Bearish FVG - look for price touching zone from below
            return candle['high'] >= zone_low and candle['close'] < zone_high
    
    def _generate_trade_signal(self, candle: Dict, zone: List[float], direction: str, fvg_time: datetime) -> Optional[Dict]:
        """
        Generate trade signal based on FVG retest
        """
        zone_low, zone_high = zone
        entry_price = candle['close']
        
        if direction == 'bullish':
            # Long trade
            stop_loss = zone_low - (zone_high - zone_low) * 0.1  # 10% below zone
            take_profit = entry_price + (entry_price - stop_loss) * 2  # 2:1 R:R
            
            return {
                'timestamp': candle['timestamp'],
                'direction': 'LONG',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'fvg_time': fvg_time,
                'zone': zone
            }
        else:
            # Short trade
            stop_loss = zone_high + (zone_high - zone_low) * 0.1  # 10% above zone
            take_profit = entry_price - (stop_loss - entry_price) * 2  # 2:1 R:R
            
            return {
                'timestamp': candle['timestamp'],
                'direction': 'SHORT',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'fvg_time': fvg_time,
                'zone': zone
            }
    
    def _execute_trades(self, df: pd.DataFrame, signals: List[Dict]):
        """
        Execute trades based on signals
        """
        balance = self.initial_capital
        
        for signal in signals:
            entry_time = signal['timestamp']
            direction = signal['direction']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            
            # Calculate position size based on risk
            risk_amount = balance * self.risk_per_trade
            price_risk = abs(entry_price - stop_loss)
            
            if price_risk > 0:
                position_size = risk_amount / price_risk
            else:
                continue
                
            # Find exit point
            future_candles = df[df['timestamp'] > entry_time]
            exit_info = self._find_exit_point(future_candles, direction, stop_loss, take_profit)
            
            if exit_info:
                # Calculate P&L
                if direction == 'LONG':
                    pnl = (exit_info['exit_price'] - entry_price) * position_size
                else:
                    pnl = (entry_price - exit_info['exit_price']) * position_size
                
                # R-multiple
                r_mult = pnl / risk_amount
                
                # Update balance
                balance += pnl
                
                # Record trade
                trade = {
                    'entry_time': entry_time,
                    'exit_time': exit_info['exit_time'],
                    'direction': direction,
                    'entry_price': entry_price,
                    'exit_price': exit_info['exit_price'],
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'position_size': position_size,
                    'pnl': pnl,
                    'r_mult': r_mult,
                    'exit_reason': exit_info['reason'],
                    'balance': balance,
                    'risk_amount': risk_amount
                }
                
                self.trades.append(trade)
                
                # Update equity curve
                self.equity_curve.append({
                    'timestamp': exit_info['exit_time'],
                    'balance': balance,
                    'pnl': pnl
                })
    
    def _find_exit_point(self, future_candles: pd.DataFrame, direction: str, stop_loss: float, take_profit: float) -> Optional[Dict]:
        """
        Find exit point for trade
        """
        max_bars = 100  # Maximum bars to hold trade
        
        for i, (idx, candle) in enumerate(future_candles.iterrows()):
            if i >= max_bars:
                # Time-based exit
                return {
                    'exit_time': candle['timestamp'],
                    'exit_price': candle['close'],
                    'reason': 'TIME'
                }
            
            if direction == 'LONG':
                if candle['low'] <= stop_loss:
                    return {
                        'exit_time': candle['timestamp'],
                        'exit_price': stop_loss,
                        'reason': 'STOP_LOSS'
                    }
                elif candle['high'] >= take_profit:
                    return {
                        'exit_time': candle['timestamp'],
                        'exit_price': take_profit,
                        'reason': 'TAKE_PROFIT'
                    }
            else:  # SHORT
                if candle['high'] >= stop_loss:
                    return {
                        'exit_time': candle['timestamp'],
                        'exit_price': stop_loss,
                        'reason': 'STOP_LOSS'
                    }
                elif candle['low'] <= take_profit:
                    return {
                        'exit_time': candle['timestamp'],
                        'exit_price': take_profit,
                        'reason': 'TAKE_PROFIT'
                    }
        
        return None
    
    def _calculate_comprehensive_stats(self) -> Dict:
        """
        Calculate comprehensive trading statistics
        """
        if not self.trades:
            return self._generate_empty_report()
        
        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] < 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        
        # P&L metrics
        total_pnl = sum(t['pnl'] for t in self.trades)
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        
        # Win/Loss rates
        win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0
        loss_rate = (loss_count / total_trades) * 100 if total_trades > 0 else 0
        
        # Average win/loss
        avg_win = gross_profit / win_count if win_count > 0 else 0
        avg_loss = gross_loss / loss_count if loss_count > 0 else 0
        
        # Reward/Risk ratio
        reward_risk = avg_win / avg_loss if avg_loss > 0 else 0
        
        # Largest wins/losses
        largest_win = max([t['pnl'] for t in winning_trades]) if winning_trades else 0
        largest_loss = min([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Profit factor
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Returns
        final_balance = self.equity_curve[-1]['balance'] if self.equity_curve else self.initial_capital
        total_return = ((final_balance - self.initial_capital) / self.initial_capital) * 100
        
        # Calculate drawdown
        max_drawdown, max_drawdown_pct = self._calculate_drawdown()
        
        # Calculate ratios
        returns = [t['pnl']/self.initial_capital for t in self.trades]
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)
        
        # Kelly Criterion
        kelly_criterion = self._calculate_kelly_criterion(winning_trades, losing_trades)
        
        # Expectancy
        expectancy = (win_rate/100 * avg_win) - (loss_rate/100 * avg_loss)
        
        # Generate report
        report = {
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate': win_rate,
            'loss_rate': loss_rate,
            'total_pnl': total_pnl,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'reward_risk': reward_risk,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'profit_factor': profit_factor,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'kelly_criterion': kelly_criterion,
            'expectancy': expectancy,
            'final_balance': final_balance,
            'trades': self.trades
        }
        
        self._print_comprehensive_report(report)
        return report
    
    def _calculate_drawdown(self) -> tuple:
        """
        Calculate maximum drawdown
        """
        if not self.equity_curve:
            return 0, 0
        
        balances = [point['balance'] for point in self.equity_curve]
        peak = self.initial_capital
        max_drawdown = 0
        max_drawdown_pct = 0
        
        for balance in balances:
            if balance > peak:
                peak = balance
            
            drawdown = peak - balance
            drawdown_pct = (drawdown / peak) * 100
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct
        
        return max_drawdown, max_drawdown_pct
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """
        Calculate Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0
        
        return (mean_return / std_return) * np.sqrt(252)  # Annualized
    
    def _calculate_sortino_ratio(self, returns: List[float]) -> float:
        """
        Calculate Sortino ratio
        """
        if not returns or len(returns) < 2:
            return 0
        
        mean_return = np.mean(returns)
        negative_returns = [r for r in returns if r < 0]
        
        if not negative_returns:
            return 0
        
        downside_std = np.std(negative_returns)
        
        if downside_std == 0:
            return 0
        
        return (mean_return / downside_std) * np.sqrt(252)  # Annualized
    
    def _calculate_kelly_criterion(self, winning_trades: List[Dict], losing_trades: List[Dict]) -> float:
        """
        Calculate Kelly Criterion
        """
        if not winning_trades or not losing_trades:
            return 0
        
        win_prob = len(winning_trades) / (len(winning_trades) + len(losing_trades))
        loss_prob = 1 - win_prob
        
        avg_win = np.mean([t['pnl'] for t in winning_trades])
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades]))
        
        if avg_loss == 0:
            return 0
        
        win_loss_ratio = avg_win / avg_loss
        kelly = win_prob - (loss_prob / win_loss_ratio)
        
        return kelly * 100  # As percentage
    
    def _print_comprehensive_report(self, report: Dict):
        """
        Print comprehensive statistical report
        """
        print("\n📊 COMPREHENSIVE STATISTICAL ANALYSIS")
        print("=" * 70)
        
        print("\n💰 PERFORMANCE METRICS")
        print("-" * 50)
        print(f"Net Profit/Loss: ${report['total_pnl']:,.2f}")
        print(f"Gross Profit: ${report['gross_profit']:,.2f}")
        print(f"Gross Loss: ${report['gross_loss']:,.2f}")
        print(f"Total Return: {report['total_return']:.2f}%")
        print(f"Final Balance: ${report['final_balance']:,.2f}")
        
        print("\n📈 TRADE STATISTICS")
        print("-" * 50)
        print(f"Total Trades: {report['total_trades']}")
        print(f"Winning Trades: {report['winning_trades']}")
        print(f"Losing Trades: {report['losing_trades']}")
        print(f"Win Rate: {report['win_rate']:.2f}%")
        print(f"Loss Rate: {report['loss_rate']:.2f}%")
        
        print("\n🎯 WIN/LOSS ANALYSIS")
        print("-" * 50)
        print(f"Average Win: ${report['avg_win']:,.2f}")
        print(f"Average Loss: ${report['avg_loss']:,.2f}")
        print(f"Reward/Risk Ratio: {report['reward_risk']:.2f}")
        print(f"Largest Win: ${report['largest_win']:,.2f}")
        print(f"Largest Loss: ${report['largest_loss']:,.2f}")
        
        print("\n🛡️ RISK METRICS")
        print("-" * 50)
        print(f"Maximum Drawdown: ${report['max_drawdown']:,.2f}")
        print(f"Maximum Drawdown %: {report['max_drawdown_pct']:.2f}%")
        print(f"Profit Factor: {report['profit_factor']:.2f}")
        
        print("\n📊 ADVANCED RATIOS")
        print("-" * 50)
        print(f"Sharpe Ratio: {report['sharpe_ratio']:.2f}")
        print(f"Sortino Ratio: {report['sortino_ratio']:.2f}")
        print(f"Kelly Criterion: {report['kelly_criterion']:.2f}%")
        print(f"Expectancy: ${report['expectancy']:.2f}")
        
        # Entries summary table
        print("\n📋 ENTRIES SUMMARY TABLE")
        print("=" * 120)
        print(f"{'#':<3} {'Date':<12} {'Time':<8} {'Dir':<5} {'Entry':<10} {'Stop':<10} {'Target':<10} {'Exit':<10} {'P&L':<10} {'R-Mult':<8} {'Reason':<10}")
        print("=" * 120)
        
        for i, trade in enumerate(report['trades'][:20], 1):  # Show first 20 trades
            entry_date = trade['entry_time'].strftime('%Y-%m-%d')
            entry_time = trade['entry_time'].strftime('%H:%M:%S')
            
            print(f"{i:<3} {entry_date:<12} {entry_time:<8} {trade['direction']:<5} "
                  f"{trade['entry_price']:<10.2f} {trade['stop_loss']:<10.2f} {trade['take_profit']:<10.2f} "
                  f"{trade['exit_price']:<10.2f} {trade['pnl']:<10.2f} {trade['r_mult']:<8.2f} {trade['exit_reason']:<10}")
        
        if len(report['trades']) > 20:
            print(f"... and {len(report['trades']) - 20} more trades")
        
        print("=" * 120)
    
    def _generate_empty_report(self) -> Dict:
        """
        Generate empty report for no trades
        """
        empty_report = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'loss_rate': 0,
            'total_pnl': 0,
            'gross_profit': 0,
            'gross_loss': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'reward_risk': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'profit_factor': 0,
            'total_return': 0,
            'max_drawdown': 0,
            'max_drawdown_pct': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'kelly_criterion': 0,
            'expectancy': 0,
            'final_balance': self.initial_capital,
            'trades': []
        }
        
        self._print_comprehensive_report(empty_report)
        return empty_report


def main():
    """
    Main function to run the backtest
    """
    backtester = WorkingStatisticalBacktester()
    
    # Run backtest for recent period with data
    start_date = "2025-06-17"
    end_date = "2025-07-17"
    
    result = backtester.run_backtest("BTC/USD", start_date, end_date)
    
    print("\n✅ WORKING STATISTICAL BACKTEST COMPLETED")
    print("=" * 70)
    print("📊 ALL COMPREHENSIVE METRICS CALCULATED")
    print("📋 DETAILED ENTRIES TABLE PROVIDED")
    print("🎯 READY FOR ANALYSIS")


if __name__ == "__main__":
    main()
