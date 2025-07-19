# tests/conftest.py
"""Pytest configuration and shared fixtures."""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock, Mock

from core.data.models import (
    Candle,
    FVGZone,
    SignalDirection,
    TimeFrame,
)
from core.indicators.fvg_detector import (
    FVGDetector,
    FVGFilterConfig,
)

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Test Data Fixtures
@pytest.fixture
def sample_candles():
    """Sample candle data for testing."""
    candles = []
    base_time = datetime(2023, 1, 1, 12, 0, 0)

    for i in range(5):
        timestamp = base_time + timedelta(minutes=i)
        candles.append(
            Candle(
                timestamp=timestamp,
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50050"),
                volume=Decimal("1000"),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1,
            )
        )

    return candles


@pytest.fixture
def sample_fvg_zone() -> FVGZone:
    """Generate a sample FVG zone for testing."""
    return FVGZone(
        timestamp=datetime(2025, 1, 1, 9, 30),
        symbol="BTC/USD",
        timeframe=TimeFrame.MINUTE_15,
        direction=SignalDirection.LONG,
        zone_high=Decimal("50300"),
        zone_low=Decimal("50200"),
        strength=0.75,
        confidence=0.85,
        status="active",
        touch_count=0,
        created_candle_index=2,
        metadata={"quality": "high"},
    )


@pytest.fixture
def fvg_detector() -> FVGDetector:
    """Create an FVG detector instance for testing."""
    config = FVGFilterConfig(
        min_zone_size_percentage=0.01,
        min_strength_threshold=0.5,
        high_quality_threshold=0.7,
        premium_quality_threshold=0.85,
    )
    return FVGDetector(config=config)


# Mock Objects
@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = Mock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.exists.return_value = False
    mock.delete.return_value = True
    return mock


@pytest.fixture
def mock_database():
    """Mock database connection for testing."""
    mock = AsyncMock()
    mock.execute.return_value = True
    mock.fetch.return_value = []
    mock.fetchrow.return_value = None
    return mock


@pytest.fixture
def mock_alpaca_client():
    """Mock Alpaca API client for testing."""
    mock = Mock()
    mock.get_bars.return_value = []
    mock.submit_order.return_value = Mock(id="test-order-123")
    mock.get_positions.return_value = []
    return mock


# Test Helpers
def assert_candle_valid(candle: Candle) -> None:
    """Assert that a candle has valid OHLCV data."""
    assert candle.high >= candle.open
    assert candle.high >= candle.close
    assert candle.low <= candle.open
    assert candle.low <= candle.close
    assert candle.volume >= 0


def assert_fvg_valid(fvg: FVGZone) -> None:
    """Assert that an FVG zone has valid data."""
    assert fvg.zone_high > fvg.zone_low
    assert fvg.strength >= 0.0
    assert fvg.strength <= 1.0
    assert fvg.confidence >= 0.0
    assert fvg.confidence <= 1.0
    assert fvg.direction in [SignalDirection.LONG, SignalDirection.SHORT]
    assert fvg.status in ["active", "touched", "invalidated"]


def create_test_candles(
    base_price: Decimal = Decimal("50000"),
    pattern: str = "normal",
    volume_profile: str = "medium",
    count: int = 10,
) -> List[Candle]:
    """Create test candles with specific patterns."""
    candles = []
    base_time = datetime(2025, 1, 1, 9, 0)

    for i in range(count):
        timestamp = base_time + timedelta(minutes=15 * i)

        if pattern == "bullish_fvg" and i == 2:
            # Create a bullish FVG on the 3rd candle
            open_price = base_price + Decimal("300")  # Gap up
            high_price = open_price + Decimal("100")
            low_price = open_price - Decimal("50")
            close_price = open_price + Decimal("75")
        elif pattern == "bearish_fvg" and i == 2:
            # Create a bearish FVG on the 3rd candle
            open_price = base_price - Decimal("300")  # Gap down
            high_price = open_price + Decimal("50")
            low_price = open_price - Decimal("100")
            close_price = open_price - Decimal("75")
        else:
            # Normal price action
            price_variance = Decimal(str(50 * (i % 3 - 1)))
            open_price = base_price + price_variance
            high_price = open_price + Decimal("50")
            low_price = open_price - Decimal("50")
            close_price = open_price + Decimal(str(25 * (1 if i % 2 == 0 else -1)))

        # Volume based on profile
        if volume_profile == "high":
            volume = Decimal(str(2000 + i * 100))
        elif volume_profile == "low":
            volume = Decimal(str(500 + i * 25))
        else:  # medium
            volume = Decimal(str(1000 + i * 50))

        candles.append(
            Candle(
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
            )
        )

    return candles


if __name__ == "__main__":
    # Run basic fixture tests
    pytest.main([__file__, "-v"])
