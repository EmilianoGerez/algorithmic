#!/usr/bin/env python3
"""
Simple Time Window Backtesting with Database Flushing
Clean approach that processes data chronologically without pre-populated pools
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal
from src.db.models.fvg import FVG
from src.db.models.pivot import Pivot


class CleanTimeWindowBacktester:
    """
    Clean backtesting approach that:
    1. Flushes database before each test
    2. Processes data chronologically
    3. Only uses data available at each timestamp
    4. No pre-populated pools
    """
    
    def __init__(self):
        self.repo = AlpacaCryptoRepository()
        self.redis = get_redis_connection()
        self.db = SessionLocal()
        self.service = SignalDetectionService(self.repo, self.redis, self.db)
    
    def flush_database(self):
        """Flush all FVG and Pivot data from database"""
        print("🧹 Flushing database...")
        
        try:
            # Delete all FVG records
            fvg_count = self.db.query(FVG).count()
            self.db.query(FVG).delete()
            
            # Delete all Pivot records
            pivot_count = self.db.query(Pivot).count()
            self.db.query(Pivot).delete()
            
            # Commit changes
            self.db.commit()
            
            print(f"   ✅ Deleted {fvg_count} FVG records")
            print(f"   ✅ Deleted {pivot_count} Pivot records")
            
        except Exception as e:
            print(f"   ❌ Error flushing database: {e}")
            self.db.rollback()
    
    def flush_cache(self):
        """Flush Redis cache"""
        print("🧹 Flushing Redis cache...")
        
        try:
            # Get all keys related to our data
            keys = self.redis.keys("*BTC/USD*")
            keys.extend(self.redis.keys("*fvg*"))
            keys.extend(self.redis.keys("*pivot*"))
            
            if keys:
                self.redis.delete(*keys)
                print(f"   ✅ Deleted {len(keys)} cache entries")
            else:
                print(f"   ✅ No cache entries to delete")
                
        except Exception as e:
            print(f"   ❌ Error flushing cache: {e}")
    
    def backtest_time_window(self, symbol: str, ltf: str, htf: str, start: str, end: str) -> Dict:
        """
        Clean time window backtesting
        """
        print(f"🚀 Starting Clean Time Window Backtesting")
        print(f"   Symbol: {symbol}")
        print(f"   LTF: {ltf}, HTF: {htf}")
        print(f"   Period: {start} to {end}")
        
        # Step 1: Clean slate
        self.flush_database()
        self.flush_cache()
        
        # Step 2: Get raw data for the entire period
        print(f"\n📥 Loading raw data...")
        
        # Get LTF data
        ltf_result = self.service.detect_signals(
            symbol=symbol,
            signal_type="fvg_and_pivot",
            timeframe=ltf,
            start=start,
            end=end
        )
        ltf_candles = ltf_result["candles"]
        
        # Get HTF data (extended lookback for context)
        htf_start = (pd.to_datetime(start) - timedelta(days=30)).isoformat() + "Z"
        htf_result = self.service.detect_signals(
            symbol=symbol,
            signal_type="fvg_and_pivot", 
            timeframe=htf,
            start=htf_start,
            end=end
        )
        htf_candles = htf_result["candles"]
        
        print(f"   📊 LTF Candles: {len(ltf_candles)}")
        print(f"   📊 HTF Candles: {len(htf_candles)}")
        
        # Step 3: Process data chronologically
        results = self._process_chronologically(ltf_candles, htf_candles, symbol, ltf, htf)
        
        return results
    
    def _process_chronologically(self, ltf_candles: List[Dict], htf_candles: List[Dict], 
                               symbol: str, ltf: str, htf: str) -> Dict:
        """
        Process candles in chronological order, simulating real-time
        """
        print(f"\n🔄 Processing chronologically...")
        
        # Convert to DataFrames
        ltf_df = pd.DataFrame(ltf_candles)
        ltf_df['timestamp'] = pd.to_datetime(ltf_df['timestamp'], utc=True)
        ltf_df = ltf_df.sort_values('timestamp').reset_index(drop=True)
        
        htf_df = pd.DataFrame(htf_candles)
        htf_df['timestamp'] = pd.to_datetime(htf_df['timestamp'], utc=True)
        htf_df = htf_df.sort_values('timestamp').reset_index(drop=True)
        
        # Track detected FVGs and signals
        detected_fvgs = []
        signals = []
        
        # Process each LTF candle
        for i, ltf_candle in ltf_df.iterrows():
            current_time = ltf_candle['timestamp']
            
            # Progress indicator
            if i % 200 == 0:
                print(f"   Processing candle {i}/{len(ltf_df)} - {current_time}")
            
            # Get HTF context up to current time
            htf_context = htf_df[htf_df['timestamp'] <= current_time]
            
            if len(htf_context) < 10:  # Need minimum HTF context
                continue
            
            # Detect FVGs in HTF context (real-time detection)
            current_fvgs = self._detect_fvgs_realtime(htf_context.to_dict('records'), current_time)
            
            # Add newly detected FVGs to our list
            for fvg in current_fvgs:
                if fvg not in detected_fvgs:
                    detected_fvgs.append(fvg)
            
            # Check for FVG interactions with current LTF candle
            if detected_fvgs:
                # Get LTF history up to current time
                ltf_history = ltf_df[ltf_df['timestamp'] <= current_time]
                
                # Check for signal opportunities
                signal = self._check_signal_opportunity(
                    ltf_candle, 
                    ltf_history.to_dict('records'), 
                    detected_fvgs,
                    current_time
                )
                
                if signal:
                    signals.append(signal)
                    print(f"   ✅ Signal detected at {current_time}")
        
        print(f"✅ Chronological processing complete")
        
        return {
            'signals': signals,
            'detected_fvgs': detected_fvgs,
            'ltf_candles_processed': len(ltf_df),
            'htf_candles_processed': len(htf_df)
        }
    
    def _detect_fvgs_realtime(self, htf_candles: List[Dict], current_time: datetime) -> List[Dict]:
        """
        Detect FVGs in real-time from HTF candles
        Only returns newly detected FVGs
        """
        if len(htf_candles) < 3:
            return []
        
        # Look for FVG in the last 3 candles
        recent_candles = htf_candles[-3:]
        
        # Check for FVG pattern
        fvgs = []
        
        if len(recent_candles) >= 3:
            candle1, candle2, candle3 = recent_candles
            
            # Bullish FVG: candle1 high < candle3 low
            if candle1['high'] < candle3['low']:
                fvg = {
                    'timestamp': candle2['timestamp'],
                    'zone_low': candle1['high'],
                    'zone_high': candle3['low'],
                    'direction': 'bullish',
                    'detected_at': current_time.isoformat() + 'Z'
                }
                fvgs.append(fvg)
            
            # Bearish FVG: candle1 low > candle3 high
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
    
    def _check_signal_opportunity(self, ltf_candle: Dict, ltf_history: List[Dict], 
                                fvgs: List[Dict], current_time: datetime) -> Optional[Dict]:
        """
        Check if current LTF candle creates a signal opportunity
        """
        # Check if LTF candle touches any FVG
        for fvg in fvgs:
            # Only check FVGs that existed before current time
            fvg_time = pd.to_datetime(fvg['timestamp'], utc=True)
            if fvg_time > current_time:
                continue
            
            # Check if candle touches FVG zone
            if (ltf_candle['low'] <= fvg['zone_high'] and 
                ltf_candle['high'] >= fvg['zone_low']):
                
                # FVG touch detected - check for signal conditions
                signal = self._evaluate_signal_conditions(ltf_candle, ltf_history, fvg, current_time)
                
                if signal:
                    return signal
        
        return None
    
    def _evaluate_signal_conditions(self, ltf_candle: Dict, ltf_history: List[Dict], 
                                  fvg: Dict, current_time: datetime) -> Optional[Dict]:
        """
        Evaluate if FVG touch meets signal conditions
        """
        if len(ltf_history) < 50:  # Need enough history for EMAs
            return None
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(ltf_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Find current candle index
        current_idx = len(df) - 1
        
        # Look for swing point formation (simplified)
        if current_idx < 5:  # Need some history
            return None
        
        # Check for swing point in last few candles
        swing_point = self._detect_swing_point_simple(df, current_idx, fvg['direction'])
        
        if not swing_point:
            return None
        
        # Check EMA conditions
        ema_signal = self._check_ema_conditions(df, fvg['direction'])
        
        if not ema_signal:
            return None
        
        # Generate signal
        return {
            'timestamp': current_time.isoformat() + 'Z',
            'symbol': 'BTC/USD',
            'direction': fvg['direction'],
            'entry_price': ltf_candle['close'],
            'fvg_zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}",
            'swing_point': swing_point,
            'ema_signal': ema_signal,
            'confidence': 0.75
        }
    
    def _detect_swing_point_simple(self, df: pd.DataFrame, current_idx: int, fvg_direction: str) -> Optional[Dict]:
        """
        Simple swing point detection
        """
        if current_idx < 3:
            return None
        
        # Look at last 3 candles
        lookback = 3
        start_idx = max(0, current_idx - lookback)
        
        if fvg_direction == 'bearish':
            # Look for swing high
            highest_idx = start_idx
            highest_price = df.iloc[start_idx]['high']
            
            for i in range(start_idx, current_idx + 1):
                if df.iloc[i]['high'] > highest_price:
                    highest_price = df.iloc[i]['high']
                    highest_idx = i
            
            return {
                'type': 'swing_high',
                'price': highest_price,
                'timestamp': df.iloc[highest_idx]['timestamp'].isoformat() + 'Z'
            }
        else:
            # Look for swing low
            lowest_idx = start_idx
            lowest_price = df.iloc[start_idx]['low']
            
            for i in range(start_idx, current_idx + 1):
                if df.iloc[i]['low'] < lowest_price:
                    lowest_price = df.iloc[i]['low']
                    lowest_idx = i
            
            return {
                'type': 'swing_low',
                'price': lowest_price,
                'timestamp': df.iloc[lowest_idx]['timestamp'].isoformat() + 'Z'
            }
    
    def _check_ema_conditions(self, df: pd.DataFrame, fvg_direction: str) -> Optional[Dict]:
        """
        Check EMA crossover conditions
        """
        if len(df) < 20:
            return None
        
        # Calculate EMAs
        df = df.copy()
        df['ema_9'] = df['close'].ewm(span=9).mean()
        df['ema_20'] = df['close'].ewm(span=20).mean()
        
        # Check recent EMA conditions
        recent_candles = df.tail(10)
        
        for i in range(1, len(recent_candles)):
            current = recent_candles.iloc[i]
            previous = recent_candles.iloc[i-1]
            
            # Check for crossover
            if (previous['ema_9'] <= previous['ema_20'] and 
                current['ema_9'] > current['ema_20']):
                # Bullish crossover
                if fvg_direction == 'bearish':  # Bearish FVG expects bullish crossover
                    return {
                        'type': 'bullish_crossover',
                        'timestamp': current['timestamp'].isoformat() + 'Z',
                        'ema_9': current['ema_9'],
                        'ema_20': current['ema_20']
                    }
            elif (previous['ema_9'] >= previous['ema_20'] and 
                  current['ema_9'] < current['ema_20']):
                # Bearish crossover
                if fvg_direction == 'bullish':  # Bullish FVG expects bearish crossover
                    return {
                        'type': 'bearish_crossover',
                        'timestamp': current['timestamp'].isoformat() + 'Z',
                        'ema_9': current['ema_9'],
                        'ema_20': current['ema_20']
                    }
        
        return None
    
    def cleanup(self):
        """Clean up resources"""
        self.db.close()


def test_clean_backtesting():
    """Test the clean backtesting approach"""
    
    print("🚀 Testing Clean Time Window Backtesting")
    print("=" * 80)
    
    # Initialize backtester
    backtester = CleanTimeWindowBacktester()
    
    try:
        # Test on the May 29 period where we know the signal exists
        results = backtester.backtest_time_window(
            symbol="BTC/USD",
            ltf="15T",
            htf="4H",
            start="2025-05-29T12:00:00Z",
            end="2025-05-30T00:00:00Z"
        )
        
        print(f"\n📊 Backtesting Results:")
        print(f"   🎯 Signals Found: {len(results['signals'])}")
        print(f"   📈 FVGs Detected: {len(results['detected_fvgs'])}")
        print(f"   📊 LTF Candles Processed: {results['ltf_candles_processed']}")
        print(f"   📊 HTF Candles Processed: {results['htf_candles_processed']}")
        
        if results['signals']:
            print(f"\n🎯 Signal Details:")
            for i, signal in enumerate(results['signals']):
                print(f"   Signal {i+1}:")
                print(f"      • Time: {signal['timestamp']}")
                print(f"      • Direction: {signal['direction']}")
                print(f"      • Entry Price: {signal['entry_price']:.2f}")
                print(f"      • FVG Zone: {signal['fvg_zone']}")
                print(f"      • Confidence: {signal['confidence']:.2f}")
        
        if results['detected_fvgs']:
            print(f"\n📈 FVG Detection Summary:")
            for i, fvg in enumerate(results['detected_fvgs'][:5]):  # Show first 5
                print(f"   FVG {i+1}: {fvg['timestamp']} - {fvg['zone_low']:.2f}-{fvg['zone_high']:.2f} ({fvg['direction']})")
        
    except Exception as e:
        print(f"❌ Error in backtesting: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        backtester.cleanup()
    
    print(f"\n✅ Clean backtesting test complete!")


if __name__ == "__main__":
    test_clean_backtesting()
