#!/usr/bin/env python3
"""
Simple Clean Backtesting - No External Dependencies
Processes data chronologically with database flushing
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


class SimpleCleanBacktester:
    """
    Simple clean backtesting without external dependencies
    """
    
    def __init__(self):
        self.repo = AlpacaCryptoRepository()
        self.redis = get_redis_connection()
        self.db = SessionLocal()
        self.service = SignalDetectionService(self.repo, self.redis, self.db)
    
    def flush_database(self):
        """Flush database and cache"""
        print("🧹 Flushing database and cache...")
        
        try:
            # Delete database records
            fvg_count = self.db.query(FVG).count()
            pivot_count = self.db.query(Pivot).count()
            
            self.db.query(FVG).delete()
            self.db.query(Pivot).delete()
            self.db.commit()
            
            # Clear cache
            try:
                keys = self.redis.keys("*BTC*")
                if keys:
                    self.redis.delete(*keys)
                print(f"   ✅ Deleted {fvg_count} FVGs, {pivot_count} Pivots, {len(keys)} cache entries")
            except:
                print(f"   ✅ Deleted {fvg_count} FVGs, {pivot_count} Pivots")
                
        except Exception as e:
            print(f"   ❌ Error flushing: {e}")
            self.db.rollback()
    
    def backtest_simple(self, symbol: str, ltf: str, start: str, end: str) -> Dict:
        """
        Simple backtesting with chronological processing
        """
        print(f"🚀 Simple Clean Backtesting")
        print(f"   Symbol: {symbol}, LTF: {ltf}")
        print(f"   Period: {start} to {end}")
        
        # Clean slate
        self.flush_database()
        
        # Get data
        try:
            ltf_result = self.service.detect_signals(
                symbol=symbol,
                signal_type="fvg_and_pivot",
                timeframe=ltf,
                start=start,
                end=end
            )
            ltf_candles = ltf_result["candles"]
            print(f"   📊 LTF Candles: {len(ltf_candles)}")
            
        except Exception as e:
            return {"error": f"Data fetch failed: {e}"}
        
        # Process chronologically
        results = self._process_chronologically(ltf_candles, symbol)
        
        return results
    
    def _process_chronologically(self, ltf_candles: List[Dict], symbol: str) -> Dict:
        """
        Process candles chronologically 
        """
        print(f"🔄 Processing {len(ltf_candles)} candles chronologically...")
        
        df = pd.DataFrame(ltf_candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        signals = []
        fvgs_detected = []
        
        # Process each candle
        for i, candle in df.iterrows():
            current_time = candle['timestamp']
            
            if i % 100 == 0:
                print(f"   Processing candle {i}/{len(df)} - {current_time}")
            
            # Get HTF context up to current time
            htf_context = self._get_htf_context(current_time, symbol)
            
            # Detect FVGs in HTF context
            new_fvgs = self._detect_fvgs_in_context(htf_context, current_time)
            
            for fvg in new_fvgs:
                if fvg not in fvgs_detected:
                    fvgs_detected.append(fvg)
            
            # Check for signals
            if fvgs_detected:
                ltf_history = df[df['timestamp'] <= current_time]
                
                signal = self._check_for_signal(candle, ltf_history, fvgs_detected)
                
                if signal:
                    signals.append(signal)
                    print(f"   ✅ Signal at {current_time}: {signal['direction']}")
        
        print(f"✅ Processing complete")
        
        return {
            'signals': signals,
            'fvgs_detected': fvgs_detected,
            'candles_processed': len(df)
        }
    
    def _get_htf_context(self, current_time: datetime, symbol: str) -> List[Dict]:
        """
        Get HTF context available at current time
        """
        # Get HTF data for last 30 days
        start_time = current_time - timedelta(days=30)
        
        try:
            htf_result = self.service.detect_signals(
                symbol=symbol,
                signal_type="fvg_and_pivot",
                timeframe="4H",
                start=start_time.isoformat() + "Z",
                end=current_time.isoformat() + "Z"
            )
            return htf_result["candles"]
        except:
            return []
    
    def _detect_fvgs_in_context(self, htf_candles: List[Dict], current_time: datetime) -> List[Dict]:
        """
        Detect FVGs in HTF context
        """
        if len(htf_candles) < 3:
            return []
        
        fvgs = []
        
        # Check last 3 candles for FVG pattern
        for i in range(len(htf_candles) - 2):
            candle1 = htf_candles[i]
            candle2 = htf_candles[i + 1]
            candle3 = htf_candles[i + 2]
            
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
    
    def _check_for_signal(self, candle: Dict, ltf_history: pd.DataFrame, fvgs: List[Dict]) -> Optional[Dict]:
        """
        Check if current candle creates a signal
        """
        # Check FVG touches
        for fvg in fvgs:
            if (candle['low'] <= fvg['zone_high'] and 
                candle['high'] >= fvg['zone_low']):
                
                # FVG touched - check conditions
                if len(ltf_history) >= 50:  # Need history for EMAs
                    
                    # Calculate EMAs
                    ltf_history = ltf_history.copy()
                    ltf_history['ema_9'] = ltf_history['close'].ewm(span=9).mean()
                    ltf_history['ema_20'] = ltf_history['close'].ewm(span=20).mean()
                    
                    # Check for crossover in recent candles
                    recent = ltf_history.tail(10)
                    
                    for j in range(1, len(recent)):
                        curr = recent.iloc[j]
                        prev = recent.iloc[j-1]
                        
                        # Bullish crossover
                        if (prev['ema_9'] <= prev['ema_20'] and 
                            curr['ema_9'] > curr['ema_20']):
                            
                            if fvg['direction'] == 'bearish':
                                return {
                                    'timestamp': candle['timestamp'],
                                    'direction': 'bullish',
                                    'entry_price': candle['close'],
                                    'fvg_zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}",
                                    'ema_9': curr['ema_9'],
                                    'ema_20': curr['ema_20'],
                                    'confidence': 0.75
                                }
                        
                        # Bearish crossover
                        elif (prev['ema_9'] >= prev['ema_20'] and 
                              curr['ema_9'] < curr['ema_20']):
                            
                            if fvg['direction'] == 'bullish':
                                return {
                                    'timestamp': candle['timestamp'],
                                    'direction': 'bearish',
                                    'entry_price': candle['close'],
                                    'fvg_zone': f"{fvg['zone_low']:.2f}-{fvg['zone_high']:.2f}",
                                    'ema_9': curr['ema_9'],
                                    'ema_20': curr['ema_20'],
                                    'confidence': 0.75
                                }
        
        return None
    
    def cleanup(self):
        """Clean up resources"""
        self.db.close()


def test_simple_clean_backtesting():
    """Test simple clean backtesting"""
    
    print("🚀 Testing Simple Clean Backtesting")
    print("=" * 80)
    
    backtester = SimpleCleanBacktester()
    
    try:
        # Test with historical data (valid dates)
        results = backtester.backtest_simple(
            symbol="BTC/USD",
            ltf="15T",
            start="2024-01-01T00:00:00Z",
            end="2024-01-03T00:00:00Z"
        )
        
        if "error" in results:
            print(f"❌ {results['error']}")
            return
        
        print(f"\n📊 Results:")
        print(f"   🎯 Signals: {len(results['signals'])}")
        print(f"   📈 FVGs: {len(results['fvgs_detected'])}")
        print(f"   📊 Candles: {results['candles_processed']}")
        
        if results['signals']:
            print(f"\n🎯 Signal Details:")
            for i, signal in enumerate(results['signals']):
                print(f"   {i+1}. {signal['timestamp']}: {signal['direction']} at {signal['entry_price']:.2f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        backtester.cleanup()
    
    print(f"\n✅ Simple backtesting test complete!")


if __name__ == "__main__":
    test_simple_clean_backtesting()
