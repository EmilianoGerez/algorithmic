#!/usr/bin/env python3
"""Quick test to verify the Timeframe refactor works correctly."""

from datetime import UTC, datetime, timedelta

from core.entities import Candle
from core.strategy.aggregator import TimeAggregator
from core.strategy.timeframe import TimeframeConfig


def test_basic_functionality():
    """Test that basic aggregation still works after refactor."""
    # Test both old and new API
    old_api_agg = TimeAggregator(tf_minutes=60)
    new_api_agg = TimeAggregator.from_timeframe(TimeframeConfig.H1)
    
    # Create test candles
    base_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
    candles = []
    
    for i in range(61):  # 61 candles to trigger completion
        candle = Candle(
            ts=base_time + timedelta(minutes=i),
            open=100.0 + i,
            high=105.0 + i,
            low=95.0 + i,
            close=102.0 + i,
            volume=1000
        )
        candles.append(candle)
    
    # Test old API
    old_results = []
    for candle in candles:
        result = old_api_agg.update(candle)
        old_results.extend(result)
    
    # Test new API
    new_results = []
    for candle in candles:
        result = new_api_agg.update(candle)
        new_results.extend(result)
    
    # Should get same results
    assert len(old_results) == len(new_results) == 1
    
    old_candle = old_results[0]
    new_candle = new_results[0]
    
    assert old_candle.ts == new_candle.ts
    assert old_candle.open == new_candle.open
    assert old_candle.close == new_candle.close
    assert old_candle.volume == new_candle.volume
    
    # Test new bucket_id method
    test_time = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
    bucket_id = new_api_agg.timeframe.bucket_id(test_time)
    bucket_start = new_api_agg.timeframe.bucket_start(test_time)
    
    assert isinstance(bucket_id, int)
    assert bucket_start.minute == 0  # Should be start of hour
    
    print("✅ Timeframe refactor verified!")
    print(f"   Old API result: {old_candle}")
    print(f"   New API result: {new_candle}")
    print(f"   Timeframe: {new_api_agg.timeframe}")
    print(f"   Bucket ID: {bucket_id}")
    print(f"   Bucket start: {bucket_start}")


if __name__ == "__main__":
    test_basic_functionality()
