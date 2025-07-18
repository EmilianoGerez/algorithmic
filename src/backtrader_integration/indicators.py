"""
Custom Backtrader Indicators for FVG Trading
Professional indicators that integrate with existing FVG system
"""

import backtrader as bt
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class FVGIndicator(bt.Indicator):
    """
    Custom FVG indicator that detects Fair Value Gaps
    Integrates with existing FVG detection logic
    """
    
    lines = ('fvg_signal', 'fvg_zone_high', 'fvg_zone_low', 'fvg_strength')
    
    params = (
        ('lookback', 50),
        ('min_gap_size', 0.001),  # Minimum gap size as percentage
        ('max_age_hours', 24),    # Maximum age of FVG in hours
    )
    
    def __init__(self):
        self.fvg_zones = []
        self.addminperiod(3)  # Need at least 3 candles for FVG detection
    
    def next(self):
        # Initialize lines
        self.lines.fvg_signal[0] = 0
        self.lines.fvg_zone_high[0] = 0
        self.lines.fvg_zone_low[0] = 0
        self.lines.fvg_strength[0] = 0
        
        # Need at least 3 candles
        if len(self.data) < 3:
            return
        
        # Get current and previous candles
        current_candle = {
            'high': self.data.high[0],
            'low': self.data.low[0],
            'close': self.data.close[0],
            'timestamp': self.data.datetime.datetime(0)
        }
        
        prev_candle = {
            'high': self.data.high[-1],
            'low': self.data.low[-1],
            'close': self.data.close[-1]
        }
        
        prev_prev_candle = {
            'high': self.data.high[-2],
            'low': self.data.low[-2],
            'close': self.data.close[-2]
        }
        
        # Detect FVG
        fvg = self._detect_fvg(prev_prev_candle, prev_candle, current_candle)
        
        if fvg:
            # Add to active zones
            self.fvg_zones.append(fvg)
            
            # Set indicator values
            self.lines.fvg_signal[0] = 1 if fvg['direction'] == 'bullish' else -1
            self.lines.fvg_zone_high[0] = fvg['zone_high']
            self.lines.fvg_zone_low[0] = fvg['zone_low']
            self.lines.fvg_strength[0] = fvg['strength']
        
        # Clean old zones
        self._clean_old_zones()
    
    def _detect_fvg(self, candle1: Dict, candle2: Dict, candle3: Dict) -> Optional[Dict]:
        """
        Detect FVG pattern in three consecutive candles
        
        Args:
            candle1: First candle (oldest)
            candle2: Second candle (middle)
            candle3: Third candle (newest)
            
        Returns:
            FVG dictionary or None
        """
        # Bullish FVG: candle1 high < candle3 low
        if candle1['high'] < candle3['low']:
            gap_size = candle3['low'] - candle1['high']
            gap_percentage = gap_size / candle1['high']
            
            if gap_percentage >= self.params.min_gap_size:
                return {
                    'direction': 'bullish',
                    'zone_low': candle1['high'],
                    'zone_high': candle3['low'],
                    'strength': gap_percentage,
                    'timestamp': self.data.datetime.datetime(0),
                    'touches': 0
                }
        
        # Bearish FVG: candle1 low > candle3 high
        elif candle1['low'] > candle3['high']:
            gap_size = candle1['low'] - candle3['high']
            gap_percentage = gap_size / candle1['low']
            
            if gap_percentage >= self.params.min_gap_size:
                return {
                    'direction': 'bearish',
                    'zone_low': candle3['high'],
                    'zone_high': candle1['low'],
                    'strength': gap_percentage,
                    'timestamp': self.data.datetime.datetime(0),
                    'touches': 0
                }
        
        return None
    
    def _clean_old_zones(self):
        """Remove old FVG zones"""
        current_time = self.data.datetime.datetime(0)
        cutoff_time = current_time - timedelta(hours=self.params.max_age_hours)
        
        self.fvg_zones = [
            zone for zone in self.fvg_zones
            if zone['timestamp'] > cutoff_time
        ]
    
    def get_active_zones(self) -> List[Dict]:
        """Get currently active FVG zones"""
        return self.fvg_zones.copy()


class EMATrendFilter(bt.Indicator):
    """
    EMA trend filter matching the existing system
    Provides trend alignment signals
    """
    
    lines = ('trend_signal', 'trend_strength', 'ema_fast', 'ema_slow', 'ema_trend')
    
    params = (
        ('ema_fast', 9),
        ('ema_slow', 20),
        ('ema_trend', 50),
    )
    
    def __init__(self):
        # Create EMA indicators
        self.ema_fast = bt.indicators.EMA(period=self.params.ema_fast)
        self.ema_slow = bt.indicators.EMA(period=self.params.ema_slow)
        self.ema_trend = bt.indicators.EMA(period=self.params.ema_trend)
        
        # Store in lines for easy access
        self.lines.ema_fast = self.ema_fast
        self.lines.ema_slow = self.ema_slow
        self.lines.ema_trend = self.ema_trend
    
    def next(self):
        # Get current EMA values
        fast = self.ema_fast[0]
        slow = self.ema_slow[0]
        trend = self.ema_trend[0]
        
        # Bullish alignment: fast > slow > trend
        if fast > slow > trend:
            self.lines.trend_signal[0] = 1
            # Calculate strength based on EMA separation
            strength = ((fast - slow) / slow + (slow - trend) / trend) / 2
            self.lines.trend_strength[0] = min(strength, 1.0)
        
        # Bearish alignment: fast < slow < trend
        elif fast < slow < trend:
            self.lines.trend_signal[0] = -1
            # Calculate strength based on EMA separation
            strength = ((slow - fast) / fast + (trend - slow) / slow) / 2
            self.lines.trend_strength[0] = min(strength, 1.0)
        
        # No clear trend
        else:
            self.lines.trend_signal[0] = 0
            self.lines.trend_strength[0] = 0
    
    def is_bullish_aligned(self) -> bool:
        """Check if EMAs are in bullish alignment"""
        return self.lines.trend_signal[0] == 1
    
    def is_bearish_aligned(self) -> bool:
        """Check if EMAs are in bearish alignment"""
        return self.lines.trend_signal[0] == -1
    
    def get_trend_strength(self) -> float:
        """Get trend strength (0-1)"""
        return self.lines.trend_strength[0]


class NYTradingHours(bt.Indicator):
    """
    NY trading hours filter
    Matches the existing system's trading time constraints
    """
    
    lines = ('trading_hours', 'session_type')
    
    params = (
        ('timezone', 'America/New_York'),
    )
    
    def next(self):
        # Get current datetime
        dt = self.data.datetime.datetime(0)
        
        # Convert to NY time (simplified - assumes UTC input)
        hour = dt.hour
        
        # NY trading hours (as per existing system):
        # 20:00-00:00 (8 PM to 12 AM)
        # 02:00-04:00 (2 AM to 4 AM)
        # 08:00-13:00 (8 AM to 1 PM)
        
        if (20 <= hour <= 23) or (hour == 0):
            self.lines.trading_hours[0] = 1
            self.lines.session_type[0] = 1  # Evening session
        elif 2 <= hour <= 3:
            self.lines.trading_hours[0] = 1
            self.lines.session_type[0] = 2  # Early morning session
        elif 8 <= hour <= 12:
            self.lines.trading_hours[0] = 1
            self.lines.session_type[0] = 3  # Morning session
        else:
            self.lines.trading_hours[0] = 0
            self.lines.session_type[0] = 0  # Outside trading hours
    
    def is_trading_time(self) -> bool:
        """Check if current time is within trading hours"""
        return self.lines.trading_hours[0] == 1
    
    def get_session_type(self) -> int:
        """Get current session type (0=none, 1=evening, 2=early morning, 3=morning)"""
        return self.lines.session_type[0]


class SwingPointDetector(bt.Indicator):
    """
    Swing point detector for stop loss placement
    Matches the existing system's swing detection logic
    """
    
    lines = ('swing_high', 'swing_low', 'swing_signal')
    
    params = (
        ('lookback', 10),
        ('min_swing_size', 0.001),  # Minimum swing size as percentage
    )
    
    def __init__(self):
        self.addminperiod(self.params.lookback * 2 + 1)
    
    def next(self):
        # Initialize lines
        self.lines.swing_high[0] = 0
        self.lines.swing_low[0] = 0
        self.lines.swing_signal[0] = 0
        
        # Need enough data
        if len(self.data) < self.params.lookback * 2 + 1:
            return
        
        # Find swing high
        swing_high = self._find_swing_high()
        if swing_high:
            self.lines.swing_high[0] = swing_high
            self.lines.swing_signal[0] = 1
        
        # Find swing low
        swing_low = self._find_swing_low()
        if swing_low:
            self.lines.swing_low[0] = swing_low
            self.lines.swing_signal[0] = -1
    
    def _find_swing_high(self) -> Optional[float]:
        """Find swing high in recent data"""
        lookback = self.params.lookback
        
        # Check if middle point is highest
        middle_idx = lookback
        middle_high = self.data.high[-middle_idx]
        
        # Check left side
        for i in range(1, lookback + 1):
            if self.data.high[-middle_idx - i] >= middle_high:
                return None
        
        # Check right side
        for i in range(1, lookback + 1):
            if self.data.high[-middle_idx + i] >= middle_high:
                return None
        
        return middle_high
    
    def _find_swing_low(self) -> Optional[float]:
        """Find swing low in recent data"""
        lookback = self.params.lookback
        
        # Check if middle point is lowest
        middle_idx = lookback
        middle_low = self.data.low[-middle_idx]
        
        # Check left side
        for i in range(1, lookback + 1):
            if self.data.low[-middle_idx - i] <= middle_low:
                return None
        
        # Check right side
        for i in range(1, lookback + 1):
            if self.data.low[-middle_idx + i] <= middle_low:
                return None
        
        return middle_low
    
    def get_last_swing_high(self) -> float:
        """Get the last swing high"""
        # Look back through recent data
        for i in range(len(self.data)):
            if len(self.data) > i and self.lines.swing_high[-i] > 0:
                return self.lines.swing_high[-i]
        
        # Fallback to recent high
        return max(self.data.high.get(ago=i) for i in range(min(20, len(self.data))))
    
    def get_last_swing_low(self) -> float:
        """Get the last swing low"""
        # Look back through recent data
        for i in range(len(self.data)):
            if len(self.data) > i and self.lines.swing_low[-i] > 0:
                return self.lines.swing_low[-i]
        
        # Fallback to recent low
        return min(self.data.low.get(ago=i) for i in range(min(20, len(self.data))))


class EntrySignalDetector(bt.Indicator):
    """
    Entry signal detector implementing the 2-candle EMA crossover method
    Matches the existing system's entry logic
    """
    
    lines = ('entry_signal', 'entry_strength', 'entry_price', 'signal_type')
    
    params = (
        ('ema_period', 20),
        ('confirmation_candles', 2),
    )
    
    def __init__(self):
        self.ema_20 = bt.indicators.EMA(period=self.params.ema_period)
        self.consecutive_above = 0
        self.consecutive_below = 0
        self.addminperiod(self.params.ema_period + self.params.confirmation_candles)
    
    def next(self):
        # Initialize lines
        self.lines.entry_signal[0] = 0
        self.lines.entry_strength[0] = 0
        self.lines.entry_price[0] = 0
        self.lines.signal_type[0] = 0
        
        current_close = self.data.close[0]
        ema_20 = self.ema_20[0]
        
        # Track consecutive candles above/below EMA 20
        if current_close > ema_20:
            self.consecutive_above += 1
            self.consecutive_below = 0
        elif current_close < ema_20:
            self.consecutive_below += 1
            self.consecutive_above = 0
        else:
            self.consecutive_above = 0
            self.consecutive_below = 0
        
        # Check for bullish entry signal (2 consecutive candles above EMA 20)
        if self.consecutive_above >= self.params.confirmation_candles:
            self.lines.entry_signal[0] = 1
            self.lines.entry_strength[0] = min(self.consecutive_above / 5.0, 1.0)
            self.lines.entry_price[0] = current_close
            self.lines.signal_type[0] = 1  # Bullish
        
        # Check for bearish entry signal (2 consecutive candles below EMA 20)
        elif self.consecutive_below >= self.params.confirmation_candles:
            self.lines.entry_signal[0] = -1
            self.lines.entry_strength[0] = min(self.consecutive_below / 5.0, 1.0)
            self.lines.entry_price[0] = current_close
            self.lines.signal_type[0] = -1  # Bearish
    
    def has_bullish_signal(self) -> bool:
        """Check if there's a bullish entry signal"""
        return self.lines.entry_signal[0] == 1
    
    def has_bearish_signal(self) -> bool:
        """Check if there's a bearish entry signal"""
        return self.lines.entry_signal[0] == -1
    
    def get_signal_strength(self) -> float:
        """Get signal strength (0-1)"""
        return self.lines.entry_strength[0]


class RiskManager(bt.Indicator):
    """
    Risk management indicator
    Calculates position sizes and risk metrics
    """
    
    lines = ('position_size', 'risk_amount', 'reward_amount', 'risk_reward_ratio')
    
    params = (
        ('risk_per_trade', 0.02),  # 2% risk per trade
        ('reward_risk_ratio', 2.0),  # 1:2 risk-reward ratio
        ('max_position_size', 0.1),  # Maximum 10% position size
    )
    
    def __init__(self):
        self.current_portfolio_value = 0
    
    def next(self):
        # Initialize lines
        self.lines.position_size[0] = 0
        self.lines.risk_amount[0] = 0
        self.lines.reward_amount[0] = 0
        self.lines.risk_reward_ratio[0] = 0
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, 
                              portfolio_value: float) -> Tuple[float, float, float]:
        """
        Calculate position size based on risk parameters
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            portfolio_value: Current portfolio value
            
        Returns:
            Tuple of (position_size, risk_amount, reward_amount)
        """
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share <= 0:
            return 0, 0, 0
        
        # Calculate risk amount
        risk_amount = portfolio_value * self.params.risk_per_trade
        
        # Calculate position size
        position_size = risk_amount / risk_per_share
        
        # Apply maximum position size constraint
        max_position_value = portfolio_value * self.params.max_position_size
        max_position_size = max_position_value / entry_price
        
        position_size = min(position_size, max_position_size)
        
        # Calculate actual risk and reward
        actual_risk = position_size * risk_per_share
        reward_amount = actual_risk * self.params.reward_risk_ratio
        
        return position_size, actual_risk, reward_amount
    
    def get_take_profit(self, entry_price: float, stop_loss: float, 
                       direction: str) -> float:
        """
        Calculate take profit level
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            direction: 'long' or 'short'
            
        Returns:
            Take profit price
        """
        risk_per_share = abs(entry_price - stop_loss)
        reward_per_share = risk_per_share * self.params.reward_risk_ratio
        
        if direction == 'long':
            return entry_price + reward_per_share
        else:
            return entry_price - reward_per_share


if __name__ == "__main__":
    # Test indicators
    print("🧪 Testing Custom Indicators...")
    
    # This would be tested within a Backtrader strategy
    print("✅ Indicators defined successfully!")
    print("   - FVGIndicator: Detects Fair Value Gaps")
    print("   - EMATrendFilter: Provides trend alignment")
    print("   - NYTradingHours: Filters trading hours")
    print("   - SwingPointDetector: Finds swing points")
    print("   - EntrySignalDetector: Detects entry signals")
    print("   - RiskManager: Manages position sizing")
