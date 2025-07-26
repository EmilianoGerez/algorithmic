#!/usr/bin/env python3
"""Test the new Timeframe refactor with self-contained bucket_id method."""

from datetime import UTC, datetime

from core.entities import Candle
from core.strategy.aggregator import TimeAggregator
from core.strategy.timeframe import TimeframeConfig


def test_timeframe_refactor():
    """Test the new Timeframe-based aggregator API."""
    # Test the new from_timeframe class method
    h1_aggregator = TimeAggregator.from_timeframe(TimeframeConfig.H1)
    
    # Verify it has the correct configuration
    assert h1_aggregator.tf_minutes == 60
    assert h1_aggregator.timeframe.name == "H1"
    assert h1_aggregator.timeframe.minutes == 60
    
    # Test self-contained bucket_id method
    test_timestamp = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
    bucket_id = h1_aggregator.timeframe.bucket_id(test_timestamp)
    
    # Verify it's the same as the old method
    from core.strategy.timeframe import get_bucket_id
    old_bucket_id = get_bucket_id(test_timestamp, 60)
    assert bucket_id == old_bucket_id
    
    # Test bucket_start method
    bucket_start = h1_aggregator.timeframe.bucket_start(test_timestamp)
    expected_start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
    assert bucket_start == expected_start
    
    # Test aggregation still works
    candles = []
    for minute in range(60):
        ts = datetime(2024, 1, 1, 10, minute, 0, tzinfo=UTC)
        candle = Candle(
            ts=ts,
            open=100.0 + minute,
            high=105.0 + minute, 
            low=95.0 + minute,
            close=102.0 + minute,
            volume=1000
        )
        candles.append(candle)
    
    # Process candles
    completed = []
    for candle in candles:
        result = h1_aggregator.update(candle)
        completed.extend(result)
    
    # Should have no completed candles yet (need next hour to trigger)
    assert len(completed) == 0
    
    # Add one candle from next hour to trigger completion
    next_hour_candle = Candle(
        ts=datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC),
        open=200.0,
        high=205.0,
        low=195.0,
        close=202.0,
        volume=1000
    )
    result = h1_aggregator.update(next_hour_candle)
    completed.extend(result)
    
    # Should have 1 completed H1 candle
    assert len(completed) == 1
    h1_candle = completed[0]
    
    assert h1_candle.ts == datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
    assert h1_candle.open == 100.0  # First minute
    assert h1_candle.close == 161.0  # Last minute (102.0 + 59)
    assert h1_candle.volume == 60000  # 60 * 1000
    
    print("✅ Timeframe refactor test passed!")
    print(f"   H1 bucket_id: {bucket_id}")
    print(f"   H1 bucket_start: {bucket_start}")
    print(f"   H1 candle: {h1_candle}")


if __name__ == "__main__":
    test_timeframe_refactor()
