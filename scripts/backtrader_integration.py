#!/usr/bin/env python3
"""
Backtrader Integration for Clean Backtesting
Uses Backtrader framework with Alpaca data for proper chronological processing
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Backtrader imports
try:
    import backtrader as bt
    import backtrader.indicators as btind
    BACKTRADER_AVAILABLE = True
except ImportError:
    print("⚠️ Backtrader not installed. Install with: pip install backtrader")
    BACKTRADER_AVAILABLE = False

from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


class AlpacaDataFeed(bt.feeds.PandasData):
    """
    Custom Backtrader data feed for Alpaca data
    """
    params = (
        ('datetime', 'timestamp'),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
    )


class FVGStrategy(bt.Strategy):
    """
    Backtrader strategy for FVG + EMA crossover signals
    """
    
    params = (
        ('ema_fast', 9),
        ('ema_slow', 20),
        ('htf_lookback', 30),  # days
        ('printlog', True),
    )
    
    def __init__(self):
        # Initialize indicators
        self.ema_fast = btind.EMA(self.data.close, period=self.params.ema_fast)
        self.ema_slow = btind.EMA(self.data.close, period=self.params.ema_slow)
        
        # Track FVGs and signals
        self.detected_fvgs = []
        self.signals_generated = []
        self.htf_candles = []
        
        # Initialize data service for HTF data
        repo = AlpacaCryptoRepository()
        redis = get_redis_connection()
        db = SessionLocal()
        self.data_service = SignalDetectionService(repo, redis, db)
        
        self.log(f"Strategy initialized with EMA periods: {self.params.ema_fast}/{self.params.ema_slow}")
    
    def log(self, txt, dt=None):
        """Logging function"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}: {txt}')
    
    def next(self):
        """
        Called for each bar - this is where chronological processing happens
        """
        current_time = self.datas[0].datetime.datetime(0)
        current_price = self.data.close[0]
        
        # Get HTF context for current time (this simulates real-time HTF data availability)
        htf_context = self._get_htf_context(current_time)
        
        # Detect FVGs in HTF context
        new_fvgs = self._detect_fvgs_realtime(htf_context, current_time)
        
        # Add new FVGs to our list
        for fvg in new_fvgs:
            if fvg not in self.detected_fvgs:
                self.detected_fvgs.append(fvg)
                self.log(f"FVG detected: {fvg['direction']} {fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}")
        
        # Check for FVG touches
        for fvg in self.detected_fvgs:
            if self._check_fvg_touch(fvg, current_price):
                # FVG touched - check for signal conditions
                if self._check_signal_conditions(fvg, current_time):
                    self._generate_signal(fvg, current_time, current_price)
    
    def _get_htf_context(self, current_time: datetime) -> List[Dict]:
        """
        Get HTF context that would be available at current_time
        This simulates real-time HTF data availability
        """
        # Calculate lookback period
        lookback_start = current_time - timedelta(days=self.params.htf_lookback)
        
        try:
            # Get HTF data up to current time
            htf_result = self.data_service.detect_signals(
                symbol="BTC/USD",
                signal_type="fvg_and_pivot",
                timeframe="4H",
                start=lookback_start.isoformat() + "Z",
                end=current_time.isoformat() + "Z"
            )
            
            return htf_result["candles"]
            
        except Exception as e:
            self.log(f"Error getting HTF context: {e}")
            return []
    
    def _detect_fvgs_realtime(self, htf_candles: List[Dict], current_time: datetime) -> List[Dict]:
        """
        Detect FVGs in real-time from HTF candles
        """
        if len(htf_candles) < 3:
            return []
        
        # Look for FVG in the last 3 candles
        recent_candles = htf_candles[-3:]
        fvgs = []
        
        if len(recent_candles) >= 3:
            candle1, candle2, candle3 = recent_candles
            
            # Bullish FVG
            if candle1['high'] < candle3['low']:
                fvg = {
                    'timestamp': candle2['timestamp'],
                    'zone_low': candle1['high'],
                    'zone_high': candle3['low'],
                    'direction': 'bullish',
                    'detected_at': current_time.isoformat() + 'Z'
                }
                fvgs.append(fvg)
            
            # Bearish FVG
            elif candle1['low'] > candle3['high']:
                fvg = {
                    'timestamp': candle2['timestamp'],
                    'zone_low': candle3['high'],
                    'zone_high': candle1['low'],
                    'direction': 'bearish',
                    'detected_at': current_time.isoformat() + 'Z'
                }
                fvgs.append(fvg)
        
        return fvgs
    
    def _check_fvg_touch(self, fvg: Dict, current_price: float) -> bool:
        """
        Check if current price touches FVG zone
        """
        current_high = self.data.high[0]
        current_low = self.data.low[0]
        
        return (current_low <= fvg['zone_high'] and 
                current_high >= fvg['zone_low'])
    
    def _check_signal_conditions(self, fvg: Dict, current_time: datetime) -> bool:
        """
        Check if signal conditions are met
        """
        # Check if we have enough data for EMAs
        if len(self.data) < max(self.params.ema_fast, self.params.ema_slow):
            return False
        
        # Check EMA crossover conditions
        if fvg['direction'] == 'bearish':
            # For bearish FVG, expect bullish EMA crossover
            if (self.ema_fast[0] > self.ema_slow[0] and 
                self.ema_fast[-1] <= self.ema_slow[-1]):
                return True
        
        elif fvg['direction'] == 'bullish':
            # For bullish FVG, expect bearish EMA crossover
            if (self.ema_fast[0] < self.ema_slow[0] and 
                self.ema_fast[-1] >= self.ema_slow[-1]):
                return True
        
        return False
    
    def _generate_signal(self, fvg: Dict, current_time: datetime, current_price: float):
        """
        Generate and record a signal
        """
        signal = {
            'timestamp': current_time.isoformat() + 'Z',
            'direction': fvg['direction'],
            'entry_price': current_price,
            'fvg_zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}",
            'ema_fast': self.ema_fast[0],
            'ema_slow': self.ema_slow[0],
            'confidence': 0.75
        }
        
        self.signals_generated.append(signal)
        self.log(f"SIGNAL GENERATED: {signal['direction']} at {current_price:.2f}")
        
        # Place order in Backtrader
        if fvg['direction'] == 'bullish':
            self.buy()
        else:
            self.sell()
    
    def stop(self):
        """
        Called when strategy stops
        """
        self.log(f"Strategy completed. Signals generated: {len(self.signals_generated)}")
        
        # Print signal summary
        for i, signal in enumerate(self.signals_generated):
            self.log(f"Signal {i+1}: {signal['direction']} at {signal['entry_price']:.2f}")


class BacktraderBacktester:
    """
    Backtrader-based backtesting system
    """
    
    def __init__(self):
        self.repo = AlpacaCryptoRepository()
        self.redis = get_redis_connection()
        self.db = SessionLocal()
        self.service = SignalDetectionService(self.repo, self.redis, self.db)
    
    def backtest_time_window(self, symbol: str, ltf: str, start: str, end: str) -> Dict:
        """
        Run backtest using Backtrader framework
        """
        if not BACKTRADER_AVAILABLE:
            return {"error": "Backtrader not available"}
        
        print(f"🚀 Starting Backtrader Backtesting")
        print(f"   Symbol: {symbol}")
        print(f"   Timeframe: {ltf}")
        print(f"   Period: {start} to {end}")
        
        # Get LTF data
        ltf_result = self.service.detect_signals(
            symbol=symbol,
            signal_type="fvg_and_pivot",
            timeframe=ltf,
            start=start,
            end=end
        )
        ltf_candles = ltf_result["candles"]
        
        print(f"   📊 LTF Candles: {len(ltf_candles)}")
        
        # Convert to DataFrame
        df = pd.DataFrame(ltf_candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.set_index('timestamp')
        
        # Create Backtrader cerebro
        cerebro = bt.Cerebro()
        
        # Add data feed
        data_feed = AlpacaDataFeed(dataname=df)
        cerebro.adddata(data_feed)
        
        # Add strategy
        cerebro.addstrategy(FVGStrategy)
        
        # Set cash and commission
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.001)
        
        # Run backtest
        print(f"🔄 Running backtest...")
        
        results = cerebro.run()
        strategy_instance = results[0]
        
        # Get final portfolio value
        final_value = cerebro.broker.getvalue()
        
        return {
            'signals': strategy_instance.signals_generated,
            'detected_fvgs': strategy_instance.detected_fvgs,
            'final_value': final_value,
            'initial_cash': 10000.0,
            'return_pct': ((final_value - 10000.0) / 10000.0) * 100
        }
    
    def cleanup(self):
        """Clean up resources"""
        self.db.close()


def test_backtrader_integration():
    """Test Backtrader integration"""
    
    print("🚀 Testing Backtrader Integration")
    print("=" * 80)
    
    if not BACKTRADER_AVAILABLE:
        print("❌ Backtrader not available. Install with: pip install backtrader")
        return
    
    # Initialize backtester
    backtester = BacktraderBacktester()
    
    try:
        # Test on historical data (use valid historical dates)
        results = backtester.backtest_time_window(
            symbol="BTC/USD",
            ltf="15T",
            start="2024-01-01T00:00:00Z",
            end="2024-01-07T00:00:00Z"
        )
        
        if "error" in results:
            print(f"❌ Error: {results['error']}")
            return
        
        print(f"\n📊 Backtrader Results:")
        print(f"   🎯 Signals Generated: {len(results['signals'])}")
        print(f"   📈 FVGs Detected: {len(results['detected_fvgs'])}")
        print(f"   💰 Final Value: ${results['final_value']:.2f}")
        print(f"   📈 Return: {results['return_pct']:.2f}%")
        
        if results['signals']:
            print(f"\n🎯 Signal Details:")
            for i, signal in enumerate(results['signals']):
                print(f"   Signal {i+1}: {signal['direction']} at {signal['entry_price']:.2f}")
        
    except Exception as e:
        print(f"❌ Error in backtesting: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        backtester.cleanup()
    
    print(f"\n✅ Backtrader integration test complete!")


if __name__ == "__main__":
    test_backtrader_integration()
