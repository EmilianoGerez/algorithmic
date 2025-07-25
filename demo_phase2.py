"""Demo script for Phase 2: TimeAggregator validation.

Validates the acceptance criteria:
- 121 1-minute bars should produce exactly 2 complete H1 candles
- Performance: 500k bars processed under 1 second
- Memory efficiency: Ring buffer keeps memory bounded
"""

import time
from datetime import datetime, timezone, timedelta
from typing import List, Generator

from core.entities import Candle
from core.strategy.aggregator import TimeAggregator, MultiTimeframeAggregator


def create_sample_candles(start_time: datetime, count: int) -> List[Candle]:
    """Create realistic sample 1-minute candles for testing."""
    candles = []
    base_price = 100.0
    
    for i in range(count):
        timestamp = start_time + timedelta(minutes=i)
        
        # Simulate realistic price movement
        price_change = (i % 10) * 0.1 - 0.5  # Small oscillations
        current_price = base_price + price_change + (i * 0.01)  # Slight uptrend
        
        candle = Candle(
            ts=timestamp,
            open=current_price,
            high=current_price + 0.5,
            low=current_price - 0.3,
            close=current_price + 0.2,
            volume=1000 + (i % 500)  # Variable volume
        )
        candles.append(candle)
    
    return candles


def demo_acceptance_criteria() -> bool:
    """Demo: 121 1-minute bars → 2 H1 candles."""
    print("=== Phase 2 Acceptance Criteria Demo ===")
    print("Input: 121 1-minute candles")
    print("Expected: Exactly 2 complete H1 candles")
    print()
    
    # Create TimeAggregator for H1
    aggregator = TimeAggregator(tf_minutes=60)
    
    # Create 121 1-minute candles (2 complete hours + 1 minute)
    start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    candles = create_sample_candles(start_time, 121)
    
    print(f"Created {len(candles)} 1-minute candles")
    print(f"Time range: {candles[0].ts} to {candles[-1].ts}")
    print()
    
    # Process candles and collect results
    completed_h1_candles = []
    
    for i, candle in enumerate(candles):
        result = aggregator.update(candle)
        if result:
            completed_h1_candles.extend(result)
            print(f"✅ H1 candle completed at minute {i+1}")
            for h1_candle in result:
                print(f"   H1: {h1_candle.ts} | O:{h1_candle.open:.2f} H:{h1_candle.high:.2f} L:{h1_candle.low:.2f} C:{h1_candle.close:.2f} V:{h1_candle.volume}")
    
    print()
    print(f"✅ RESULT: {len(completed_h1_candles)} H1 candles completed")
    print(f"✅ ACCEPTANCE CRITERIA: {'PASSED' if len(completed_h1_candles) == 2 else 'FAILED'}")
    print()
    
    # Verify timing
    if len(completed_h1_candles) >= 2:
        h1_1 = completed_h1_candles[0]
        h1_2 = completed_h1_candles[1]
        
        print("H1 Candle Verification:")
        print(f"  First H1:  {h1_1.ts} (should be 10:00 UTC)")
        print(f"  Second H1: {h1_2.ts} (should be 11:00 UTC)")
        
        expected_1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        expected_2 = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        
        timing_correct = (h1_1.ts == expected_1 and h1_2.ts == expected_2)
        print(f"  Timing: {'CORRECT' if timing_correct else 'INCORRECT'}")
    
    return len(completed_h1_candles) == 2


def demo_multi_timeframe() -> bool:
    """Demo: Multi-timeframe aggregation."""
    print("\n=== Multi-Timeframe Aggregation Demo ===")
    print("Aggregating to H1, H4, and D1 simultaneously")
    print()
    
    # Create multi-timeframe aggregator
    multi_agg = MultiTimeframeAggregator([60, 240, 1440])  # H1, H4, D1
    
    print(f"Timeframes: {multi_agg.timeframe_names}")
    
    # Create 8 hours of data (480 minutes)
    start_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    candles = create_sample_candles(start_time, 480)
    
    print(f"Processing {len(candles)} 1-minute candles...")
    
    # Track completed candles by timeframe
    completed_counts = {tf: 0 for tf in multi_agg.timeframe_names}
    
    for candle in candles:
        results = multi_agg.update(candle)
        
        for tf_name, tf_candles in results.items():
            if tf_candles:
                completed_counts[tf_name] += len(tf_candles)
                for tf_candle in tf_candles:
                    print(f"✅ {tf_name} completed: {tf_candle.ts} | C:{tf_candle.close:.2f}")
    
    print(f"\nCompleted candles by timeframe:")
    for tf_name, count in completed_counts.items():
        print(f"  {tf_name}: {count} candles")
    
    # Expected: 7 H1 (8:00-14:59, 15:00 incomplete), 1 H4 (8:00-11:59), 0 D1 (day incomplete)
    expected = {"H1": 7, "H4": 1, "D1": 0}
    
    print(f"\nExpected vs Actual:")
    all_correct = True
    for tf_name in multi_agg.timeframe_names:
        actual = completed_counts[tf_name]
        exp = expected[tf_name]
        correct = actual == exp
        all_correct = all_correct and correct
        print(f"  {tf_name}: Expected {exp}, Got {actual} {'✅' if correct else '❌'}")
    
    print(f"\nMulti-timeframe test: {'PASSED' if all_correct else 'FAILED'}")
    return all_correct


def demo_performance() -> bool:
    """Demo: Performance test with 500k candles."""
    print("\n=== Performance Test Demo ===")
    print("Target: Process 500k 1-minute candles under 1 second")
    print()
    
    # Create aggregator
    aggregator = TimeAggregator(tf_minutes=60, buffer_size=100)  # Smaller buffer for stress test
    
    # Create 500k candles
    print("Creating 500,000 1-minute candles...")
    start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    # Use a generator to avoid memory issues
    def generate_candles(count: int) -> Generator[Candle, None, None]:
        base_price = 100.0
        for i in range(count):
            timestamp = start_time + timedelta(minutes=i)
            yield Candle(
                ts=timestamp,
                open=base_price + (i % 100) * 0.01,
                high=base_price + (i % 100) * 0.01 + 0.5,
                low=base_price + (i % 100) * 0.01 - 0.3,
                close=base_price + (i % 100) * 0.01 + 0.2,
                volume=1000
            )
    
    # Process candles and measure time
    start_processing = time.time()
    completed_count = 0
    
    print("Processing 500k candles...")
    for i, candle in enumerate(generate_candles(500_000)):
        result = aggregator.update(candle)
        completed_count += len(result)
        
        # Print progress every 100k candles
        if (i + 1) % 100_000 == 0:
            elapsed = time.time() - start_processing
            print(f"  Processed {i+1:,} candles in {elapsed:.2f}s")
    
    end_processing = time.time()
    total_time = end_processing - start_processing
    
    print(f"\n✅ Performance Results:")
    print(f"  Total candles processed: 500,000")
    print(f"  H1 candles completed: {completed_count:,}")
    print(f"  Processing time: {total_time:.3f} seconds")
    print(f"  Throughput: {500_000 / total_time:,.0f} candles/second")
    print(f"  Target (<1s): {'PASSED' if total_time < 1.0 else 'FAILED'}")
    
    return total_time < 1.0


def demo_memory_efficiency() -> bool:
    """Demo: Memory efficiency with ring buffer."""
    print("\n=== Memory Efficiency Demo ===")
    print("Ring buffer keeps memory usage bounded regardless of input size")
    print()
    
    # Create aggregator with small buffer
    buffer_size = 100
    aggregator = TimeAggregator(tf_minutes=60, buffer_size=buffer_size)
    
    print(f"Buffer size limit: {buffer_size} candles")
    
    # Process many candles
    start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    
    for i in range(500):  # 500 minutes = 8+ hours
        timestamp = start_time + timedelta(minutes=i)
        candle = Candle(
            ts=timestamp,
            open=100.0 + i * 0.01,
            high=101.0 + i * 0.01,
            low=99.0 + i * 0.01,
            close=100.5 + i * 0.01,
            volume=1000
        )
        
        aggregator.update(candle)
        
        # Check buffer size periodically
        if i % 100 == 99:
            buffer_len = len(aggregator._buffer)
            print(f"  After {i+1} candles: buffer size = {buffer_len} (limit: {buffer_size})")
    
    final_buffer_size = len(aggregator._buffer)
    print(f"\n✅ Final buffer size: {final_buffer_size} (limit: {buffer_size})")
    print(f"✅ Memory bounded: {'PASSED' if final_buffer_size <= buffer_size else 'FAILED'}")
    
    return final_buffer_size <= buffer_size


def main() -> bool:
    """Run all Phase 2 demos."""
    print("🚀 Phase 2: TimeAggregator Validation Suite")
    print("=" * 50)
    
    # Run all demos
    results = []
    
    results.append(("Acceptance Criteria (121→2)", demo_acceptance_criteria()))
    results.append(("Multi-timeframe", demo_multi_timeframe()))
    results.append(("Performance (500k<1s)", demo_performance()))
    results.append(("Memory Efficiency", demo_memory_efficiency()))
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 PHASE 2 VALIDATION SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:<25} {status}")
        all_passed = all_passed and passed
    
    print()
    if all_passed:
        print("🎉 ALL PHASE 2 TESTS PASSED!")
        print("✅ TimeAggregator implementation complete and validated")
        print("✅ Ready to proceed to Phase 3: HTF Detectors")
    else:
        print("❌ Some tests failed - please review implementation")
    
    return all_passed


if __name__ == "__main__":
    main()
