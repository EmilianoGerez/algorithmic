"""
Example demonstrating configurable TTL wheel constants.
"""

from datetime import timedelta

from core.strategy.ttl_wheel import (
    DAY_BUCKETS,
    HOUR_BUCKETS,
    MIN_BUCKETS,
    SEC_BUCKETS,
    TimerWheel,
    WheelConfig,
)


def test_configurable_wheel_constants():
    """Test that wheel constants can be easily configured."""
    # Verify the constants are exported and accessible
    assert SEC_BUCKETS == 60
    assert MIN_BUCKETS == 60
    assert HOUR_BUCKETS == 24
    assert DAY_BUCKETS == 7

    # Create a custom config using the constants
    custom_config = WheelConfig(
        second_slots=SEC_BUCKETS,
        minute_slots=MIN_BUCKETS,
        hour_slots=HOUR_BUCKETS,
        day_slots=DAY_BUCKETS,
        max_items_per_slot=5000,  # Higher capacity
    )

    wheel = TimerWheel(config=custom_config)
    base_time = wheel.current_time

    # Test basic functionality
    expires_at = base_time + timedelta(seconds=30)
    success = wheel.schedule("test_pool", expires_at, base_time)
    assert success

    # Advance time and check expiry
    target_time = base_time + timedelta(seconds=30)
    expired = wheel.tick(target_time)
    assert len(expired) == 1
    assert expired[0].pool_id == "test_pool"

    print(
        f"✓ TTL wheel configured with {SEC_BUCKETS}s/{MIN_BUCKETS}m/{HOUR_BUCKETS}h/{DAY_BUCKETS}d buckets"
    )


def test_wheel_capacity_calculation():
    """Test the capacity calculation uses the constants."""
    config = WheelConfig()

    # The total capacity should reflect our constants
    expected_capacity = (
        SEC_BUCKETS + (MIN_BUCKETS * 60) + (HOUR_BUCKETS * 3600) + (DAY_BUCKETS * 86400)
    )
    actual_capacity = config.total_capacity_seconds()

    assert actual_capacity == expected_capacity

    print(
        f"✓ Total wheel capacity: {actual_capacity:,} seconds ({actual_capacity / 86400:.1f} days)"
    )
