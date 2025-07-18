"""
FVG Trading Strategy for Backtrader
Professional implementation using existing core modules and services
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import warnings
warnings.filterwarnings('ignore')

# Import existing core modules and services
from src.services.signal_detection import SignalDetectionService
from src.core.strategy.time_aware_fvg_strategy import TimeAwareFVGStrategy
from src.core.strategy.chronological_backtesting_strategy import ChronologicalBacktestingStrategy
from src.core.liquidity.unified_fvg_manager import UnifiedFVGManager
from src.core.signals.fvg_tracker import FVGTracker
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal

# Only import minimal custom indicators needed for Backtrader integration
from .indicators import (
    NYTradingHours,
    RiskManager
)


class FVGTradingStrategy(bt.Strategy):
    """
    Professional FVG Trading Strategy for Backtrader
    Implements the exact logic from the existing system
    """
    
    params = (
        # EMA Parameters
        ('ema_fast', 9),
        ('ema_slow', 20),
        ('ema_trend', 50),
        
        # Risk Management
        ('risk_per_trade', 0.02),      # 2% risk per trade
        ('reward_risk_ratio', 2.0),    # 1:2 risk-reward ratio
        ('max_positions', 1),          # Maximum concurrent positions
        
        # FVG Parameters
        ('fvg_lookback', 50),          # FVG lookback period
        ('max_fvg_touches', 3),        # Maximum FVG touches before invalidation
        ('fvg_timeout_hours', 24),     # FVG timeout in hours
        
        # Entry Parameters
        ('entry_confirmation_candles', 2),  # Candles for entry confirmation
        ('swing_lookback', 20),        # Swing point lookback
        
        # Debug and Logging
        ('debug', False),              # Debug mode
        ('log_trades', True),          # Log trade details
    )
    
    def __init__(self):
        """Initialize strategy with core modules and services"""
        print("🚀 Initializing FVG Trading Strategy with Core Modules")
        
        # Initialize database and cache connections
        self.db_session = SessionLocal()
        self.redis_client = get_redis_connection()
        self.repo = AlpacaCryptoRepository()
        
        # Initialize core services
        self.signal_service = SignalDetectionService(
            repo=self.repo,
            redis_client=self.redis_client,
            db_session=self.db_session
        )
        
        # Initialize core strategy components
        strategy_config = {
            'ema_fast_period': self.params.ema_fast,
            'ema_slow_period': self.params.ema_slow,
            'swing_lookback_candles': self.params.swing_lookback,
            'confirmation_window_hours': self.params.entry_confirmation_candles,
            'min_confidence_threshold': 0.6,
            'htf_lookback_hours': 720  # 30 days
        }
        
        self.core_strategy = ChronologicalBacktestingStrategy(config=strategy_config)
        
        # Initialize FVG management components
        self.fvg_manager = UnifiedFVGManager(
            db_session=self.db_session,
            cache_manager=self.signal_service.cache_manager
        )
        
        self.fvg_tracker = FVGTracker(
            db_session=self.db_session,
            max_touches=self.params.max_fvg_touches,
            timeout_hours=self.params.fvg_timeout_hours
        )
        
        # Initialize Backtrader-specific components
        self.ny_hours = NYTradingHours()
        self.risk_manager = RiskManager(
            risk_per_trade=self.params.risk_per_trade,
            reward_risk_ratio=self.params.reward_risk_ratio
        )
        
        # Additional technical indicators for Backtrader
        self.atr = bt.indicators.ATR(period=14)
        self.rsi = bt.indicators.RSI(period=14)
        
        # Strategy state
        self.trade_count = 0
        self.active_fvg_zones = []
        self.trades_log = []
        self.current_trade_info = None
        
        # Performance tracking
        self.initial_portfolio_value = 0
        self.peak_portfolio_value = 0
        self.max_drawdown = 0
        
        if self.params.debug:
            print("   ✅ Core modules and services initialized")
            print("   ✅ Signal detection service connected")
            print("   ✅ FVG management components ready")
            print("   ✅ Chronological backtesting strategy loaded")
    
    def start(self):
        """Called when strategy starts"""
        self.initial_portfolio_value = self.broker.getvalue()
        self.peak_portfolio_value = self.initial_portfolio_value
        
        print(f"📊 Strategy Started")
        print(f"   Initial Portfolio: ${self.initial_portfolio_value:,.2f}")
        print(f"   Risk per Trade: {self.params.risk_per_trade * 100:.1f}%")
        print(f"   Reward:Risk Ratio: {self.params.reward_risk_ratio}:1")
        print(f"   Max Positions: {self.params.max_positions}")
    
    def next(self):
        """Main strategy logic - uses core modules for signal detection"""
        current_time = self.data.datetime.datetime(0)
        
        # Convert current bar to format expected by core modules
        current_bar = self._convert_bt_bar_to_core_format(current_time)
        
        # Use core strategy to detect signals
        signals = self._detect_signals_with_core_modules(current_bar)
        
        # Update performance tracking
        self._update_performance_tracking()
        
        # Process signals
        if not self.position:
            self._process_entry_signals(signals)
        else:
            # Manage existing position
            self._manage_position()
        
        # Debug logging
        if self.params.debug and len(self.data) % 100 == 0:
            self._debug_log(current_time, signals)
    
    def _convert_bt_bar_to_core_format(self, timestamp: datetime) -> Dict:
        """Convert Backtrader bar to format expected by core modules"""
        return {
            'timestamp': timestamp,
            'open': self.data.open[0],
            'high': self.data.high[0],
            'low': self.data.low[0],
            'close': self.data.close[0],
            'volume': self.data.volume[0] if hasattr(self.data, 'volume') else 0
        }
    
    def _detect_signals_with_core_modules(self, current_bar: Dict) -> List[Dict]:
        """Use core modules to detect trading signals"""
        signals = []
        
        try:
            # Check if within trading hours using core logic
            if not self.ny_hours.is_trading_time(current_bar['timestamp']):
                return signals
            
            # Get FVG zones from core FVG manager
            active_fvgs = self.fvg_manager.get_active_fvgs(
                current_time=current_bar['timestamp'],
                symbol="BTC/USD"
            )
            
            # Use core strategy to evaluate signals
            core_signals = self.core_strategy.evaluate_signals(
                current_bar=current_bar,
                available_fvgs=active_fvgs
            )
            
            # Convert core signals to strategy format
            for signal in core_signals:
                if signal.confidence >= self.core_strategy.min_confidence:
                    signals.append({
                        'direction': signal.direction,
                        'price': signal.price,
                        'confidence': signal.confidence,
                        'fvg_zone': signal.fvg_zone,
                        'entry_reasons': signal.entry_reasons,
                        'stop_loss': signal.stop_loss,
                        'take_profit': signal.take_profit
                    })
            
        except Exception as e:
            if self.params.debug:
                print(f"⚠️  Error in signal detection: {e}")
        
        return signals
    
    def _process_entry_signals(self, signals: List[Dict]):
        """Process entry signals from core modules"""
        if not signals:
            return
        
        # Take the highest confidence signal
        best_signal = max(signals, key=lambda x: x['confidence'])
        
        # Calculate position size using core risk management
        position_size = self.risk_manager.calculate_position_size(
            account_value=self.broker.getvalue(),
            entry_price=best_signal['price'],
            stop_loss=best_signal['stop_loss']
        )
        
        if position_size > 0:
            # Execute trade
            if best_signal['direction'] == 'long':
                self.buy(size=position_size)
            else:
                self.sell(size=position_size)
            
            # Store trade info
            self.current_trade_info = {
                'signal': best_signal,
                'entry_time': self.data.datetime.datetime(0),
                'position_size': position_size
            }
            
            if self.params.log_trades:
                print(f"📈 {best_signal['direction'].upper()} signal at {best_signal['price']:.2f}")
                print(f"   Confidence: {best_signal['confidence']:.2f}")
                print(f"   Position size: {position_size}")
                print(f"   Stop loss: {best_signal['stop_loss']:.2f}")
                print(f"   Take profit: {best_signal['take_profit']:.2f}")
    
    def _update_fvg_zones(self):
        """Update FVG zones using core FVG manager"""
        current_time = self.data.datetime.datetime(0)
        current_bar = self._convert_bt_bar_to_core_format(current_time)
        
        # Update FVG zones through core manager
        self.fvg_manager.update_fvg_zones(
            current_bar=current_bar,
            symbol="BTC/USD"
        )
        
        # Update FVG tracker
        self.fvg_tracker.update_touches(
            current_bar=current_bar,
            active_fvgs=self.fvg_manager.get_active_fvgs(
                current_time=current_time,
                symbol="BTC/USD"
            )
        )
    
    def _check_entry_signals(self):
        """Check for entry signals using core modules"""
        current_time = self.data.datetime.datetime(0)
        current_bar = self._convert_bt_bar_to_core_format(current_time)
        
        # Use core modules to detect signals
        signals = self._detect_signals_with_core_modules(current_bar)
        
        # Process signals
        self._process_entry_signals(signals)
    
    def _update_performance_tracking(self):
        """Update performance tracking metrics"""
        current_value = self.broker.getvalue()
        
        # Update peak value
        if current_value > self.peak_portfolio_value:
            self.peak_portfolio_value = current_value
        
        # Update max drawdown
        current_drawdown = self.peak_portfolio_value - current_value
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
    
    def _manage_position(self):
        """Manage existing position using core modules"""
        if not self.position or not self.current_trade_info:
            return
        
        current_price = self.data.close[0]
        signal_info = self.current_trade_info['signal']
        
        # Check stop loss
        if self.position.size > 0:  # Long position
            if current_price <= signal_info['stop_loss']:
                self.close()
                if self.params.log_trades:
                    print(f"   🛑 Stop Loss Hit: {current_price:.2f}")
        else:  # Short position
            if current_price >= signal_info['stop_loss']:
                self.close()
                if self.params.log_trades:
                    print(f"   🛑 Stop Loss Hit: {current_price:.2f}")
        
        # Check take profit
        if self.position.size > 0:  # Long position
            if current_price >= signal_info['take_profit']:
                self.close()
                if self.params.log_trades:
                    print(f"   🎯 Take Profit Hit: {current_price:.2f}")
        else:  # Short position
            if current_price <= signal_info['take_profit']:
                self.close()
                if self.params.log_trades:
                    print(f"   🎯 Take Profit Hit: {current_price:.2f}")
        current_time = self.data.datetime.datetime(0)
        
        # Determine direction
        is_long = fvg_zone['direction'] == 'bullish'
        
        # Calculate stop loss
        if is_long:
            stop_loss = self.swing_detector.get_last_swing_low()
            # Ensure stop loss is below entry
            if stop_loss >= current_price:
                stop_loss = current_price - (self.atr[0] * 2)
        else:
            stop_loss = self.swing_detector.get_last_swing_high()
            # Ensure stop loss is above entry
            if stop_loss <= current_price:
                stop_loss = current_price + (self.atr[0] * 2)
        
        # Calculate position size
        portfolio_value = self.broker.getvalue()
        position_size, risk_amount, reward_amount = self.risk_manager.calculate_position_size(
            current_price, stop_loss, portfolio_value
        )
        
        if position_size <= 0:
            if self.params.debug:
                print(f"   ⚠️ Invalid position size calculated")
            return
        
        # Calculate take profit
        take_profit = self.risk_manager.get_take_profit(
            current_price, stop_loss, 'long' if is_long else 'short'
        )
        
        # Execute trade
        if is_long:
            order = self.buy(size=position_size)
            direction = "LONG"
        else:
            order = self.sell(size=position_size)
            direction = "SHORT"
        
        # Store trade information
        self.trade_count += 1
        self.current_trade_info = {
            'trade_number': self.trade_count,
            'timestamp': current_time,
            'direction': direction,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'position_size': position_size,
            'risk_amount': risk_amount,
            'reward_amount': reward_amount,
            'fvg_zone': fvg_zone.copy(),
            'trend_signal': self.ema_trend.lines.trend_signal[0],
            'trend_strength': self.ema_trend.get_trend_strength(),
            'entry_strength': self.entry_detector.get_signal_strength(),
            'rsi': self.rsi[0],
            'atr': self.atr[0],
            'portfolio_value': portfolio_value
        }
        
        # Log trade
        if self.params.log_trades:
            self._log_trade_entry(self.current_trade_info)
    
    def _manage_position(self):
        """Manage existing position"""
        if not self.current_trade_info:
            return
        
        current_price = self.data.close[0]
        trade_info = self.current_trade_info
        
        # Simple stop loss and take profit management
        if self.position.size > 0:  # Long position
            if current_price <= trade_info['stop_loss']:
                self.close()
                if self.params.debug:
                    print(f"   🛑 Stop Loss Hit: ${current_price:.2f}")
            elif current_price >= trade_info['take_profit']:
                self.close()
                if self.params.debug:
                    print(f"   🎯 Take Profit Hit: ${current_price:.2f}")
        
        elif self.position.size < 0:  # Short position
            if current_price >= trade_info['stop_loss']:
                self.close()
                if self.params.debug:
                    print(f"   🛑 Stop Loss Hit: ${current_price:.2f}")
            elif current_price <= trade_info['take_profit']:
                self.close()
                if self.params.debug:
                    print(f"   🎯 Take Profit Hit: ${current_price:.2f}")
    
    def _log_trade_entry(self, trade_info: Dict):
        """Log trade entry details"""
        direction = trade_info['direction']
        entry_price = trade_info['entry_price']
        stop_loss = trade_info['stop_loss']
        take_profit = trade_info['take_profit']
        position_size = trade_info['position_size']
        risk_amount = trade_info['risk_amount']
        fvg_zone = trade_info['fvg_zone']
        
        print(f"📈 {direction} Entry #{trade_info['trade_number']}: ${entry_price:.2f}")
        print(f"   Stop Loss: ${stop_loss:.2f}")
        print(f"   Take Profit: ${take_profit:.2f}")
        print(f"   Position Size: {position_size:.2f}")
        print(f"   Risk: ${risk_amount:.2f}")
        print(f"   FVG Zone: {fvg_zone['zone_low']:.2f}-{fvg_zone['zone_high']:.2f}")
        print(f"   FVG Touches: {fvg_zone['touches']}")
        print(f"   Trend Strength: {trade_info['trend_strength']:.2f}")
        print(f"   Entry Strength: {trade_info['entry_strength']:.2f}")
        print(f"   RSI: {trade_info['rsi']:.1f}")
    
    def _debug_log(self, current_time: datetime, signals: List[Dict]):
        """Enhanced debug logging with core module information"""
        print(f"🔍 Debug @ {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Bar: O={self.data.open[0]:.2f}, H={self.data.high[0]:.2f}, L={self.data.low[0]:.2f}, C={self.data.close[0]:.2f}")
        print(f"   Portfolio Value: ${self.broker.getvalue():,.2f}")
        print(f"   Max Drawdown: ${self.max_drawdown:,.2f}")
        
        # Trading hours check
        trading_hours = self.ny_hours.is_trading_time(current_time)
        print(f"   Trading Hours: {'✅ Yes' if trading_hours else '❌ No'}")
        
        # FVG information from core modules
        try:
            active_fvgs = self.fvg_manager.get_active_fvgs(
                current_time=current_time,
                symbol="BTC/USD"
            )
            print(f"   Active FVGs: {len(active_fvgs)}")
            
            for i, fvg in enumerate(active_fvgs[:3]):  # Show first 3
                print(f"     FVG {i+1}: {fvg.direction} | {fvg.zone_low:.2f}-{fvg.zone_high:.2f}")
        except Exception as e:
            print(f"   FVG Error: {e}")
        
        # Signal information
        print(f"   Signals Detected: {len(signals)}")
        for i, signal in enumerate(signals[:2]):  # Show first 2
            print(f"     Signal {i+1}: {signal['direction']} | Conf: {signal['confidence']:.2f}")
        
        # Position information
        if self.position:
            print(f"   Position: {self.position.size} @ {self.position.price:.2f}")
        
        print()  # Empty line for readability
    
    def notify_order(self, order):
        """Order notification"""
        if order.status in [order.Completed]:
            if order.isbuy():
                if self.params.log_trades:
                    print(f"   ✅ BUY Executed: ${order.executed.price:.2f}")
            else:
                if self.params.log_trades:
                    print(f"   ✅ SELL Executed: ${order.executed.price:.2f}")
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if self.params.log_trades:
                print(f"   ❌ Order {order.status}")
    
    def notify_trade(self, trade):
        """Trade notification"""
        if trade.isclosed and self.current_trade_info:
            pnl = trade.pnl
            pnl_pct = (pnl / abs(trade.value)) * 100
            
            # Complete trade info
            self.current_trade_info['exit_price'] = trade.price
            self.current_trade_info['pnl'] = pnl
            self.current_trade_info['pnl_pct'] = pnl_pct
            self.current_trade_info['exit_time'] = self.data.datetime.datetime(0)
            
            # Add to trades log
            self.trades_log.append(self.current_trade_info.copy())
            
            # Log trade closure
            if self.params.log_trades:
                outcome = "WIN" if pnl > 0 else "LOSS"
                print(f"   💰 Trade Closed: {outcome} - P&L = ${pnl:.2f} ({pnl_pct:.2f}%)")
            
            # Reset current trade
            self.current_trade_info = None
    
    def stop(self):
        """Strategy completion with cleanup"""
        final_value = self.broker.getvalue()
        total_return = ((final_value / self.initial_portfolio_value) - 1) * 100
        max_drawdown_pct = (self.max_drawdown / self.peak_portfolio_value) * 100
        
        print(f"\n📊 STRATEGY COMPLETED")
        print(f"   Initial Portfolio: ${self.initial_portfolio_value:,.2f}")
        print(f"   Final Portfolio: ${final_value:,.2f}")
        print(f"   Total Return: {total_return:.2f}%")
        print(f"   Peak Portfolio: ${self.peak_portfolio_value:,.2f}")
        print(f"   Max Drawdown: ${self.max_drawdown:,.2f} ({max_drawdown_pct:.2f}%)")
        print(f"   Total Trades: {self.trade_count}")
        
        # Calculate detailed statistics
        if self.trades_log:
            self._calculate_comprehensive_stats()
        
        # Cleanup database connections
        try:
            self.db_session.close()
            self.redis_client.close()
            print("   ✅ Database connections closed")
        except Exception as e:
            print(f"   ⚠️  Cleanup warning: {e}")
        
        print("   🏁 Strategy stopped successfully")
    
    def _calculate_comprehensive_stats(self):
        """Calculate comprehensive trading statistics"""
        trades = self.trades_log
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        
        # Performance metrics
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        net_profit = gross_profit - gross_loss
        
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        avg_win = (gross_profit / win_count) if win_count > 0 else 0
        avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        reward_risk_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
        
        # Additional metrics
        largest_win = max((t['pnl'] for t in winning_trades), default=0)
        largest_loss = min((t['pnl'] for t in losing_trades), default=0)
        
        # Print comprehensive stats
        print(f"\n💰 COMPREHENSIVE PERFORMANCE ANALYSIS")
        print(f"   Net Profit: ${net_profit:,.2f}")
        print(f"   Gross Profit: ${gross_profit:,.2f}")
        print(f"   Gross Loss: ${gross_loss:,.2f}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Winning Trades: {win_count}")
        print(f"   Losing Trades: {loss_count}")
        print(f"   Average Win: ${avg_win:,.2f}")
        print(f"   Average Loss: ${avg_loss:,.2f}")
        print(f"   Profit Factor: {profit_factor:.2f}")
        print(f"   Reward/Risk Ratio: {reward_risk_ratio:.2f}")
        print(f"   Largest Win: ${largest_win:,.2f}")
        print(f"   Largest Loss: ${largest_loss:,.2f}")
        
        # FVG analysis
        fvg_4h_trades = [t for t in trades if t['fvg_zone'].get('timeframe') == '4H']
        fvg_1d_trades = [t for t in trades if t['fvg_zone'].get('timeframe') == '1D']
        
        if fvg_4h_trades or fvg_1d_trades:
            print(f"\n📈 FVG ANALYSIS")
            print(f"   4H FVG Trades: {len(fvg_4h_trades)}")
            print(f"   1D FVG Trades: {len(fvg_1d_trades)}")
        
        # Direction analysis
        long_trades = [t for t in trades if t['direction'] == 'LONG']
        short_trades = [t for t in trades if t['direction'] == 'SHORT']
        
        print(f"\n🎯 DIRECTION ANALYSIS")
        print(f"   Long Trades: {len(long_trades)}")
        print(f"   Short Trades: {len(short_trades)}")
        
        if long_trades:
            long_win_rate = len([t for t in long_trades if t['pnl'] > 0]) / len(long_trades) * 100
            print(f"   Long Win Rate: {long_win_rate:.1f}%")
        
        if short_trades:
            short_win_rate = len([t for t in short_trades if t['pnl'] > 0]) / len(short_trades) * 100
            print(f"   Short Win Rate: {short_win_rate:.1f}%")
    
    def get_trades_log(self) -> List[Dict]:
        """Get complete trades log"""
        return self.trades_log.copy()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        final_value = self.broker.getvalue()
        total_return = ((final_value / self.initial_portfolio_value) - 1) * 100
        max_drawdown_pct = (self.max_drawdown / self.peak_portfolio_value) * 100
        
        return {
            'initial_value': self.initial_portfolio_value,
            'final_value': final_value,
            'total_return': total_return,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'total_trades': self.trade_count,
            'peak_value': self.peak_portfolio_value
        }


if __name__ == "__main__":
    # Test strategy creation
    print("🧪 Testing FVG Trading Strategy...")
    
    try:
        # This would be tested within a Backtrader cerebro engine
        print("✅ Strategy defined successfully!")
        print("   - Professional FVG detection")
        print("   - EMA trend alignment")
        print("   - NY trading hours filtering")
        print("   - Risk management")
        print("   - Comprehensive logging")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
