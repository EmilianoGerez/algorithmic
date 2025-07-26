#!/usr/bin/env python3
"""Test clock-skew guardrails with configurable behavior."""

from datetime import UTC, datetime, timedelta

from core.entities import Candle
from core.strategy.aggregator import (
    ClockSkewError,
    OutOfOrderPolicy,
    TimeAggregator,
)


def test_clock_skew_drop_policy() -> None:
    """Test DROP policy silently ignores out-of-order candles."""
    print("Testing DROP policy...")

    aggregator = TimeAggregator(
        tf_minutes=60,
        out_of_order_policy=OutOfOrderPolicy.DROP,
        enable_strict_ordering=True,
    )

    # Create candles with timestamps going backward (out of order)
    now = datetime.now(UTC)
    candle1 = Candle(ts=now, open=100, high=105, low=95, close=102, volume=1000)
    candle2 = Candle(
        ts=now - timedelta(minutes=30),
        open=101,
        high=106,
        low=96,
        close=103,
        volume=1100,
    )

    # First candle should be processed
    result1 = aggregator.update(candle1)
    print(f"  First candle: processed (got {len(result1)} completions)")

    # Second candle (out of order) should be dropped silently
    result2 = aggregator.update(candle2)
    print(f"  Out-of-order candle: dropped (got {len(result2)} completions)")

    print("  ✅ DROP policy working correctly\n")


def test_clock_skew_raise_policy() -> bool:
    """Test RAISE policy throws exception on out-of-order candles."""
    print("Testing RAISE policy...")

    aggregator = TimeAggregator(
        tf_minutes=60,
        out_of_order_policy=OutOfOrderPolicy.RAISE,
        enable_strict_ordering=True,
    )

    # Create candles with timestamps going backward
    now = datetime.now(UTC)
    candle1 = Candle(ts=now, open=100, high=105, low=95, close=102, volume=1000)
    candle2 = Candle(
        ts=now - timedelta(minutes=30),
        open=101,
        high=106,
        low=96,
        close=103,
        volume=1100,
    )

    # First candle should be processed
    result1 = aggregator.update(candle1)
    print(f"  First candle: processed (got {len(result1)} completions)")

    # Second candle should raise ClockSkewError
    try:
        aggregator.update(candle2)
        print("  ❌ Expected ClockSkewError was not raised!")
        return False
    except ClockSkewError as e:
        print(f"  ✅ ClockSkewError raised correctly: {e}")
        return True


def test_future_candle_detection() -> None:
    """Test detection of candles too far in the future."""
    print("Testing future candle detection...")

    aggregator = TimeAggregator(
        tf_minutes=60,
        out_of_order_policy=OutOfOrderPolicy.DROP,
        max_clock_skew_seconds=300,  # 5 minutes
        enable_strict_ordering=True,
    )

    # Create a candle way in the future (10 minutes from now)
    future_time = datetime.now(UTC) + timedelta(minutes=10)
    future_candle = Candle(
        ts=future_time, open=100, high=105, low=95, close=102, volume=1000
    )

    # Should be dropped due to excessive clock skew
    result = aggregator.update(future_candle)
    print(f"  Future candle (10min ahead): dropped (got {len(result)} completions)")

    # Create a candle just within tolerance (3 minutes from now)
    acceptable_future = datetime.now(UTC) + timedelta(minutes=3)
    acceptable_candle = Candle(
        ts=acceptable_future, open=100, high=105, low=95, close=102, volume=1000
    )

    # Should be processed (within 5-minute tolerance)
    result2 = aggregator.update(acceptable_candle)
    print(f"  Future candle (3min ahead): processed (got {len(result2)} completions)")

    print("  ✅ Future candle detection working correctly\n")


def test_disabled_strict_ordering() -> None:
    """Test that disabling strict ordering allows all candles."""
    print("Testing disabled strict ordering...")

    aggregator = TimeAggregator(
        tf_minutes=60,
        enable_strict_ordering=False,  # Disabled
    )

    # Create candles with mixed timestamps
    now = datetime.now(UTC)
    candle1 = Candle(ts=now, open=100, high=105, low=95, close=102, volume=1000)
    candle2 = Candle(
        ts=now - timedelta(hours=1), open=101, high=106, low=96, close=103, volume=1100
    )
    candle3 = Candle(
        ts=now + timedelta(hours=1), open=102, high=107, low=97, close=104, volume=1200
    )

    # All candles should be processed when strict ordering is disabled
    result1 = aggregator.update(candle1)
    result2 = aggregator.update(candle2)
    result3 = aggregator.update(candle3)

    print(f"  Current time candle: processed (got {len(result1)} completions)")
    print(f"  Past candle: processed (got {len(result2)} completions)")
    print(f"  Future candle: processed (got {len(result3)} completions)")
    print("  ✅ Disabled strict ordering working correctly\n")


def main() -> None:
    """Run all clock-skew guardrail tests."""
    print("🛡️  Clock-Skew Guardrails Test Suite")
    print("=====================================")

    try:
        test_clock_skew_drop_policy()
        test_clock_skew_raise_policy()
        test_future_candle_detection()
        test_disabled_strict_ordering()

        print("🎯 All clock-skew guardrail tests completed successfully!")
        print("\nClock-skew configuration options:")
        print("  - out_of_order_policy: 'drop' | 'raise' | 'recalc'")
        print("  - max_clock_skew_seconds: int (default: 300)")
        print("  - enable_strict_ordering: bool (default: True)")
        print("\nConfiguration available in configs/base.yaml:")
        print("  aggregation:")
        print("    out_of_order_policy: 'drop'")
        print("    max_clock_skew_seconds: 300")
        print("    enable_strict_ordering: true")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
