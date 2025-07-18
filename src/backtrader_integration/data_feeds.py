"""
Data Feed Integration for Backtrader
Bridges existing data sources with Backtrader's data feed system
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

from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


class FVGDataFeed(bt.feeds.PandasData):
    """
    Custom Backtrader data feed that integrates with existing FVG system
    Provides OHLCV data plus FVG zone information
    """
    
    # Define custom lines for FVG data
    lines = ('fvg_signal', 'fvg_zone_high', 'fvg_zone_low', 'fvg_timeframe')
    
    # Parameters for FVG detection
    params = (
        ('fvg_signal', -1),
        ('fvg_zone_high', -1),
        ('fvg_zone_low', -1),
        ('fvg_timeframe', -1),
    )
    
    def __init__(self, symbol: str, timeframe: str, start: str, end: str, **kwargs):
        """
        Initialize FVG data feed
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USD")
            timeframe: Timeframe for data (e.g., "5T")
            start: Start datetime string
            end: End datetime string
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.start = start
        self.end = end
        
        # Get data from existing system
        df = self._fetch_data_from_existing_system()
        
        # Add FVG data
        df = self._add_fvg_data(df)
        
        # Initialize parent class
        super().__init__(dataname=df, **kwargs)
    
    def _fetch_data_from_existing_system(self) -> pd.DataFrame:
        """
        Fetch OHLCV data from existing system
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Initialize existing system components
            repo = AlpacaCryptoRepository()
            redis = get_redis_connection()
            db = SessionLocal()
            service = SignalDetectionService(repo, redis, db)
            
            # Get data using existing service
            result = service.detect_signals(
                symbol=self.symbol,
                signal_type="pivot",  # Get basic candle data
                timeframe=self.timeframe,
                start=self.start,
                end=self.end
            )
            
            # Convert to DataFrame
            candles = result.get("candles", [])
            if not candles:
                raise ValueError("No candle data received")
            
            df = pd.DataFrame(candles)
            
            # Ensure required columns exist
            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Missing required column: {col}")
            
            # Convert timestamp to datetime index
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df.set_index('timestamp', inplace=True)
            
            # Sort by timestamp
            df = df.sort_index()
            
            # Clean up
            db.close()
            
            print(f"✅ Fetched {len(df)} candles from existing system")
            return df
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            # Return empty DataFrame with correct structure
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
    
    def _add_fvg_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add FVG data to the DataFrame
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            DataFrame with FVG data added
        """
        if df.empty:
            return df
        
        try:
            # Get FVG data from existing system
            fvgs_4h = self._fetch_fvg_data("4H")
            fvgs_1d = self._fetch_fvg_data("1D")
            
            # Combine all FVGs
            all_fvgs = fvgs_4h + fvgs_1d
            
            # Initialize FVG columns
            df['fvg_signal'] = 0
            df['fvg_zone_high'] = 0.0
            df['fvg_zone_low'] = 0.0
            df['fvg_timeframe'] = ""
            
            # Map FVGs to DataFrame rows
            for fvg in all_fvgs:
                try:
                    # Parse FVG timestamp
                    fvg_time = pd.to_datetime(fvg['timestamp'].replace('Z', ''), utc=True)
                    
                    # Find nearest candle
                    nearest_idx = df.index.get_indexer([fvg_time], method='nearest')[0]
                    
                    if nearest_idx != -1 and nearest_idx < len(df):
                        # Set FVG signal
                        signal_value = 1 if fvg['direction'] == 'bullish' else -1
                        df.iloc[nearest_idx, df.columns.get_loc('fvg_signal')] = signal_value
                        df.iloc[nearest_idx, df.columns.get_loc('fvg_zone_high')] = fvg['zone_high']
                        df.iloc[nearest_idx, df.columns.get_loc('fvg_zone_low')] = fvg['zone_low']
                        df.iloc[nearest_idx, df.columns.get_loc('fvg_timeframe')] = fvg.get('timeframe', '4H')
                
                except Exception as e:
                    print(f"⚠️ Error processing FVG: {e}")
                    continue
            
            fvg_count = len([f for f in all_fvgs if f])
            print(f"✅ Added {fvg_count} FVGs to data feed")
            
            return df
            
        except Exception as e:
            print(f"❌ Error adding FVG data: {e}")
            # Return DataFrame with empty FVG columns
            df['fvg_signal'] = 0
            df['fvg_zone_high'] = 0.0
            df['fvg_zone_low'] = 0.0
            df['fvg_timeframe'] = ""
            return df
    
    def _fetch_fvg_data(self, timeframe: str) -> List[Dict]:
        """
        Fetch FVG data for specific timeframe
        
        Args:
            timeframe: Timeframe for FVG detection
            
        Returns:
            List of FVG dictionaries
        """
        try:
            # Initialize existing system components
            repo = AlpacaCryptoRepository()
            redis = get_redis_connection()
            db = SessionLocal()
            service = SignalDetectionService(repo, redis, db)
            
            # Get FVG data
            result = service.detect_signals(
                symbol=self.symbol,
                signal_type="fvg_and_pivot",
                timeframe=timeframe,
                start=self.start,
                end=self.end
            )
            
            # Extract FVGs
            fvgs = result.get("fvgs_detected", [])
            
            # Add timeframe to each FVG
            for fvg in fvgs:
                fvg['timeframe'] = timeframe
            
            # Clean up
            db.close()
            
            return fvgs
            
        except Exception as e:
            print(f"❌ Error fetching FVG data for {timeframe}: {e}")
            return []


class MarketDataRepository:
    """
    Repository pattern for market data access
    Provides clean interface for data retrieval
    """
    
    def __init__(self):
        self.repo = AlpacaCryptoRepository()
        self.redis = get_redis_connection()
        self.db = SessionLocal()
        self.service = SignalDetectionService(self.repo, self.redis, self.db)
    
    def get_candle_data(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """
        Get candle data for symbol and timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            result = self.service.detect_signals(
                symbol=symbol,
                signal_type="pivot",
                timeframe=timeframe,
                start=start,
                end=end
            )
            
            candles = result.get("candles", [])
            df = pd.DataFrame(candles)
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                df.set_index('timestamp', inplace=True)
                df = df.sort_index()
            
            return df
            
        except Exception as e:
            print(f"❌ Error getting candle data: {e}")
            return pd.DataFrame()
    
    def get_fvg_zones(self, symbol: str, timeframe: str, start: str, end: str) -> List[Dict]:
        """
        Get FVG zones for symbol and timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: FVG timeframe
            start: Start datetime
            end: End datetime
            
        Returns:
            List of FVG dictionaries
        """
        try:
            result = self.service.detect_signals(
                symbol=symbol,
                signal_type="fvg_and_pivot",
                timeframe=timeframe,
                start=start,
                end=end
            )
            
            fvgs = result.get("fvgs_detected", [])
            
            # Add timeframe to each FVG
            for fvg in fvgs:
                fvg['timeframe'] = timeframe
            
            return fvgs
            
        except Exception as e:
            print(f"❌ Error getting FVG zones: {e}")
            return []
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'db'):
            self.db.close()


class BacktraderDataManager:
    """
    Manages data preparation and feeding for Backtrader
    """
    
    def __init__(self):
        self.data_repo = MarketDataRepository()
    
    def create_data_feed(self, symbol: str, timeframe: str, start: str, end: str) -> FVGDataFeed:
        """
        Create Backtrader data feed
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            
        Returns:
            FVGDataFeed instance
        """
        return FVGDataFeed(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end
        )
    
    def get_market_data(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """
        Get market data directly as DataFrame
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            
        Returns:
            DataFrame with market data
        """
        return self.data_repo.get_candle_data(symbol, timeframe, start, end)
    
    def get_fvg_data(self, symbol: str, timeframes: List[str], start: str, end: str) -> Dict[str, List[Dict]]:
        """
        Get FVG data for multiple timeframes
        
        Args:
            symbol: Trading symbol
            timeframes: List of timeframes
            start: Start datetime
            end: End datetime
            
        Returns:
            Dictionary with FVG data by timeframe
        """
        fvg_data = {}
        
        for tf in timeframes:
            fvg_data[tf] = self.data_repo.get_fvg_zones(symbol, tf, start, end)
        
        return fvg_data
    
    def cleanup(self):
        """Clean up resources"""
        self.data_repo.cleanup()


def create_sample_data(symbol: str, days: int = 30) -> pd.DataFrame:
    """
    Create sample market data for testing
    
    Args:
        symbol: Trading symbol
        days: Number of days of data
        
    Returns:
        DataFrame with sample OHLCV data
    """
    # Generate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    date_range = pd.date_range(start=start_date, end=end_date, freq='5T')
    
    # Generate sample price data
    np.random.seed(42)
    base_price = 50000 if 'BTC' in symbol else 3000
    
    data = []
    for i, timestamp in enumerate(date_range):
        # Add trend and volatility
        trend = np.sin(i * 0.001) * 1000
        volatility = np.random.normal(0, 300)
        noise = np.random.normal(0, 50)
        
        price = base_price + trend + volatility + noise
        price = max(price, 1000)  # Ensure positive price
        
        # Generate OHLCV
        open_price = price + np.random.uniform(-100, 100)
        high = price + np.random.uniform(0, 200)
        low = price - np.random.uniform(0, 200)
        close = price + np.random.uniform(-100, 100)
        volume = np.random.uniform(100, 1000)
        
        data.append({
            'timestamp': timestamp,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    
    return df


if __name__ == "__main__":
    # Test data feed creation
    print("🧪 Testing FVG Data Feed...")
    
    try:
        # Create data manager
        data_manager = BacktraderDataManager()
        
        # Create data feed
        feed = data_manager.create_data_feed(
            symbol="BTC/USD",
            timeframe="5T",
            start="2025-06-01T00:00:00Z",
            end="2025-06-07T23:59:59Z"
        )
        
        print("✅ Data feed created successfully!")
        
        # Cleanup
        data_manager.cleanup()
        
    except Exception as e:
        print(f"❌ Error testing data feed: {e}")
        import traceback
        traceback.print_exc()
