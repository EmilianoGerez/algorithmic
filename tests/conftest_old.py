# tests/conftest.py
"""Pytest configuration and shared fixtures."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any
import pandas as pd
import asyncio
from unittest.mock import Mock, AsyncMock

# Import your core modules
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data.models import Candle, TimeFrame, MarketData, Signal, SignalDirection, FVGZone
from core.indicators.fvg_detector import FVGDetector, FVGFilterConfig, FVGQuality


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_candles() -> List[Candle]:
    """Generate sample candle data for testing."""
    base_time = datetime(2025, 1, 1, 9, 0)
    candles = []
    
    for i in range(100):
        timestamp = base_time + timedelta(minutes=i * 5)
        # Create realistic OHLC data with some volatility
        base_price = 50000 + (i * 10)  # Trending up
        open_price = Decimal(str(base_price + (i % 3 - 1) * 20))
        high_price = open_price + Decimal(str(abs(i % 7) * 15))
        low_price = open_price - Decimal(str(abs(i % 5) * 12))
        close_price = Decimal(str(base_price + (i % 4 - 1.5) * 25))
        volume = Decimal(str(1000 + (i % 10) * 100))
        
        candle = Candle(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume
        )
        candles.append(candle)
    
    return candles


@pytest.fixture
def sample_market_data(sample_candles) -> MarketData:
    """Create sample market data."""
    return MarketData(
        symbol="BTC/USD",
        timeframe=TimeFrame.MINUTE_5,
        candles=sample_candles,
        metadata={"source": "test", "generated": True}
    )


@pytest.fixture
def fvg_strategy() -> FVGStrategy:
    """Create a configured FVG strategy for testing."""
    from core.strategies.factory import create_fvg_strategy_config
    config = create_fvg_strategy_config()
    return FVGStrategy(config)


@pytest.fixture
def risk_limits() -> RiskLimits:
    """Create standard risk limits for testing."""
    return RiskLimits(
        max_position_size=Decimal('0.1'),
        max_daily_loss=Decimal('0.05'),
        max_drawdown=Decimal('0.2'),
        max_positions=5,
        max_correlation=0.7,
        leverage_limit=Decimal('1.0')
    )


@pytest.fixture
def position_sizer() -> FixedRiskPositionSizer:
    """Create a position sizer for testing."""
    return FixedRiskPositionSizer(risk_per_trade=0.02)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock_redis = Mock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.keys.return_value = []
    mock_redis.ping.return_value = True
    return mock_redis


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    mock_session = Mock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.query.return_value.filter.return_value.all.return_value = []
    mock_session.commit.return_value = None
    mock_session.rollback.return_value = None
    mock_session.close.return_value = None
    return mock_session


@pytest.fixture
def sample_fvg_data() -> List[Dict[str, Any]]:
    """Generate sample FVG data for testing."""
    base_time = datetime(2025, 1, 1, 10, 0)
    fvgs = []
    
    for i in range(10):
        timestamp = base_time + timedelta(hours=i * 4)
        zone_low = 50000 + (i * 100)
        zone_high = zone_low + 150
        
        fvg = {
            "id": f"fvg_{i}",
            "symbol": "BTC/USD",
            "timeframe": "4H",
            "timestamp": timestamp,
            "direction": "bullish" if i % 2 == 0 else "bearish",
            "zone_low": zone_low,
            "zone_high": zone_high,
            "status": "active",
            "confidence": 0.8,
            "strength": 0.7,
            "touch_count": 0,
        }
        fvgs.append(fvg)
    
    return fvgs


@pytest.fixture
def sample_signals(sample_candles) -> List[Signal]:
    """Generate sample signals for testing."""
    signals = []
    
    for i, candle in enumerate(sample_candles[:10]):
        signal = Signal(
            signal_type="fvg_touch",
            direction=SignalDirection.LONG if i % 2 == 0 else SignalDirection.SHORT,
            entry_price=candle.close,
            timestamp=candle.timestamp,
            stop_loss=candle.close * Decimal('0.98'),
            take_profit=candle.close * Decimal('1.04'),
            confidence=0.75,
            metadata={
                "fvg_zone": [float(candle.close * Decimal('0.995')), 
                           float(candle.close * Decimal('1.005'))],
                "timeframe": "5T"
            }
        )
        signals.append(signal)
    
    return signals


class AsyncContextManager:
    """Helper class for async context managers in tests."""
    
    def __init__(self, return_value):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_mock_context():
    """Factory for creating async context manager mocks."""
    def _create_context(return_value):
        return AsyncContextManager(return_value)
    return _create_context


# Test categories markers
pytestmark = [
    pytest.mark.unit,  # Default marker for all tests
]


# Helper functions for tests
def assert_candle_valid(candle: Candle) -> None:
    """Assert that a candle has valid OHLC relationships."""
    assert candle.high >= max(candle.open, candle.close), "High must be >= max(open, close)"
    assert candle.low <= min(candle.open, candle.close), "Low must be <= min(open, close)"
    assert candle.volume >= 0, "Volume must be non-negative"


def assert_signal_valid(signal: Signal) -> None:
    """Assert that a signal has valid properties."""
    assert signal.entry_price > 0, "Entry price must be positive"
    assert signal.confidence >= 0 and signal.confidence <= 1, "Confidence must be between 0 and 1"
    if signal.stop_loss:
        if signal.direction == SignalDirection.LONG:
            assert signal.stop_loss < signal.entry_price, "Long stop loss must be below entry"
        else:
            assert signal.stop_loss > signal.entry_price, "Short stop loss must be above entry"


# Performance testing helpers
@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.perf_counter()
        
        def stop(self):
            self.end_time = time.perf_counter()
        
        @property
        def elapsed(self):
            if self.start_time is None or self.end_time is None:
                return None
            return self.end_time - self.start_time
    
    return Timer()
