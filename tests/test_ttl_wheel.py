"""
Unit tests for TTL wheel implementation.

Tests cover:
- Basic scheduling and expiry
- Wheel rollovers and cascading
- Out-of-order events
- Performance characteristics
- Fake clock deterministic advancement
"""

from datetime import datetime, timedelta

import pytest

from core.strategy.ttl_wheel import ScheduledExpiry, TimerWheel, WheelConfig


class TestTimerWheel:
    """Test suite for TimerWheel functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = WheelConfig(
            second_slots=60,
            minute_slots=60,
            hour_slots=24,
            day_slots=7,
            max_items_per_slot=100,
        )
        self.wheel = TimerWheel(self.config)
        self.base_time = datetime(2025, 1, 1, 12, 0, 0)  # Fixed test time
        self.wheel.current_time = self.base_time

    def test_basic_scheduling(self):
        """Test basic pool scheduling functionality."""
        # Schedule a pool to expire in 30 seconds
        expires_at = self.base_time + timedelta(seconds=30)
        result = self.wheel.schedule("pool_1", expires_at, self.base_time)

        assert result is True
        assert self.wheel.size() == 1
        assert "pool_1" in self.wheel._pool_to_expiry

    def test_duplicate_scheduling_prevention(self):
        """Test that duplicate pool IDs are rejected."""
        expires_at = self.base_time + timedelta(seconds=30)

        # First scheduling should succeed
        result1 = self.wheel.schedule("pool_1", expires_at, self.base_time)
        assert result1 is True

        # Second scheduling should fail
        result2 = self.wheel.schedule("pool_1", expires_at, self.base_time)
        assert result2 is False
        assert self.wheel.size() == 1

    def test_immediate_expiry_rejection(self):
        """Test that past expiry times are rejected."""
        # Try to schedule something that expires in the past
        expires_at = self.base_time - timedelta(seconds=10)
        result = self.wheel.schedule("pool_past", expires_at, self.base_time)

        assert result is False
        assert self.wheel.size() == 0

    def test_cancellation(self):
        """Test pool expiry cancellation."""
        expires_at = self.base_time + timedelta(seconds=30)
        self.wheel.schedule("pool_1", expires_at, self.base_time)

        # Cancel the scheduled expiry
        result = self.wheel.cancel("pool_1")
        assert result is True
        assert self.wheel.size() == 0

        # Second cancellation should fail
        result2 = self.wheel.cancel("pool_1")
        assert result2 is False

    def test_tick_advancement_1_second(self):
        """Test fake clock advancement for 1-second TTL (acceptance criterion)."""
        # Schedule pool with 1-second TTL
        expires_at = self.base_time + timedelta(seconds=1)
        self.wheel.schedule("pool_1sec", expires_at, self.base_time)

        # Advance fake clock by exactly 1 second
        new_time = self.base_time + timedelta(seconds=1)
        expired = self.wheel.tick(new_time)

        assert len(expired) == 1
        assert expired[0].pool_id == "pool_1sec"
        assert self.wheel.size() == 0

    def test_tick_advancement_multiple_seconds(self):
        """Test advancing clock by multiple seconds."""
        # Schedule pools at different intervals
        pools = [("pool_5s", 5), ("pool_10s", 10), ("pool_15s", 15)]

        for pool_id, seconds in pools:
            expires_at = self.base_time + timedelta(seconds=seconds)
            self.wheel.schedule(pool_id, expires_at, self.base_time)

        # Advance to 7 seconds - should expire pool_5s only
        expired = self.wheel.tick(self.base_time + timedelta(seconds=7))
        assert len(expired) == 1
        assert expired[0].pool_id == "pool_5s"
        assert self.wheel.size() == 2

        # Advance to 12 seconds - should expire pool_10s
        expired = self.wheel.tick(self.base_time + timedelta(seconds=12))
        assert len(expired) == 1
        assert expired[0].pool_id == "pool_10s"
        assert self.wheel.size() == 1

    def test_minute_rollover(self):
        """Test rollover from seconds to minutes wheel."""
        # Start at 59 seconds, schedule for 2 seconds later (crosses minute boundary)
        start_time = datetime(2025, 1, 1, 12, 0, 59)
        self.wheel.current_time = start_time

        expires_at = start_time + timedelta(seconds=2)  # Will be at 12:01:01
        self.wheel.schedule("pool_rollover", expires_at, start_time)

        # Advance across minute boundary
        expired = self.wheel.tick(start_time + timedelta(seconds=2))
        assert len(expired) == 1
        assert expired[0].pool_id == "pool_rollover"

    def test_hour_rollover(self):
        """Test rollover from minutes to hours wheel."""
        # Schedule something 61 minutes away (crosses hour boundary)
        expires_at = self.base_time + timedelta(minutes=61)
        self.wheel.schedule("pool_hour", expires_at, self.base_time)

        # Advance by 61 minutes
        target_time = self.base_time + timedelta(minutes=61)
        expired = self.wheel.tick(target_time)

        assert len(expired) == 1
        assert expired[0].pool_id == "pool_hour"

    def test_day_rollover(self):
        """Test rollover from hours to days wheel."""
        # Schedule something 25 hours away (crosses day boundary)
        expires_at = self.base_time + timedelta(hours=25)
        self.wheel.schedule("pool_day", expires_at, self.base_time)

        # Advance by 25 hours
        target_time = self.base_time + timedelta(hours=25)
        expired = self.wheel.tick(target_time)

        assert len(expired) == 1
        assert expired[0].pool_id == "pool_day"

    def test_expire_due_non_advancing(self):
        """Test expire_due method that doesn't advance the clock."""
        # Schedule multiple pools
        pools_data = [
            ("pool_past", -5),  # Already expired
            ("pool_now", 1),  # Expires 1 second from now
            ("pool_future", 30),  # Future expiry
        ]

        for pool_id, delta_seconds in pools_data:
            expires_at = self.base_time + timedelta(seconds=delta_seconds)
            if delta_seconds > 0:  # Only schedule future items (> 0, not >= 0)
                scheduled = self.wheel.schedule(pool_id, expires_at, self.base_time)
                assert scheduled is True

        # Check what should be expired without advancing
        check_time = self.base_time + timedelta(seconds=10)
        expired = self.wheel.expire_due(check_time)

        # Should find pool_now but not pool_future
        expired_ids = [item.pool_id for item in expired]
        assert "pool_now" in expired_ids
        assert "pool_future" not in expired_ids

        # Clock should not have advanced
        assert self.wheel.current_time == self.base_time

    def test_out_of_order_time_advancement_raises(self):
        """Test that moving time backwards raises an error."""
        future_time = self.base_time + timedelta(seconds=10)
        self.wheel.tick(future_time)

        # Try to move time backwards
        past_time = self.base_time + timedelta(seconds=5)
        with pytest.raises(ValueError, match="Time cannot go backwards"):
            self.wheel.tick(past_time)

    def test_metrics_tracking(self):
        """Test that performance metrics are tracked correctly."""
        initial_metrics = self.wheel.get_metrics()
        assert initial_metrics["total_scheduled"] == 0
        assert initial_metrics["total_expired"] == 0

        # Schedule and expire some pools
        for i in range(3):
            expires_at = self.base_time + timedelta(seconds=i + 1)
            self.wheel.schedule(f"pool_{i}", expires_at, self.base_time)

        # Advance time to expire all
        self.wheel.tick(self.base_time + timedelta(seconds=5))

        final_metrics = self.wheel.get_metrics()
        assert final_metrics["total_scheduled"] == 3
        assert final_metrics["total_expired"] == 3
        assert final_metrics["current_size"] == 0

    def test_wheel_position_calculation(self):
        """Test internal wheel position calculations."""
        # Test seconds wheel (0-59s)
        level, slot = self.wheel._calculate_wheel_position(30)
        assert level == 0  # Seconds wheel

        # Test minutes wheel (60-3599s)
        level, slot = self.wheel._calculate_wheel_position(120)  # 2 minutes
        assert level == 1  # Minutes wheel

        # Test hours wheel (3600-86399s)
        level, slot = self.wheel._calculate_wheel_position(7200)  # 2 hours
        assert level == 2  # Hours wheel

        # Test days wheel (86400s+)
        level, slot = self.wheel._calculate_wheel_position(172800)  # 2 days
        assert level == 3  # Days wheel

    @pytest.mark.parametrize("ttl_seconds", [1, 5, 30, 60, 300, 3600])
    def test_randomized_ttl_property(self, ttl_seconds):
        """Property test: randomized TTLs should never miss or double-fire."""
        pool_id = f"pool_{ttl_seconds}s"
        expires_at = self.base_time + timedelta(seconds=ttl_seconds)

        # Schedule the pool
        scheduled = self.wheel.schedule(pool_id, expires_at, self.base_time)
        assert scheduled is True

        # Advance to just before expiry - should not be expired
        pre_expiry = expires_at - timedelta(milliseconds=100)
        expired_early = self.wheel.expire_due(pre_expiry)
        early_ids = [item.pool_id for item in expired_early]
        assert pool_id not in early_ids

        # Advance to exact expiry time - should be expired
        expired_exact = self.wheel.tick(expires_at)
        exact_ids = [item.pool_id for item in expired_exact]
        assert pool_id in exact_ids

        # Advance further - should not fire again
        expired_late = self.wheel.tick(expires_at + timedelta(seconds=1))
        late_ids = [item.pool_id for item in expired_late]
        assert pool_id not in late_ids

    def test_large_batch_performance(self):
        """Test performance with large number of concurrent pools."""
        import time

        # Schedule 1000 pools with random TTLs
        start_time = time.time()
        pool_count = 1000

        for i in range(pool_count):
            ttl = (i % 300) + 1  # TTLs from 1-300 seconds
            expires_at = self.base_time + timedelta(seconds=ttl)
            self.wheel.schedule(f"perf_pool_{i}", expires_at, self.base_time)

        schedule_time = time.time() - start_time

        # Advance time to expire all pools
        start_time = time.time()
        expired = self.wheel.tick(self.base_time + timedelta(seconds=301))
        expire_time = time.time() - start_time

        # Verify all pools expired
        assert len(expired) == pool_count

        # Performance assertions (generous limits for test stability)
        assert schedule_time < 0.1  # 100ms for 1000 schedules
        assert expire_time < 0.1  # 100ms for 1000 expiries

        print(
            f"Performance: {pool_count} schedules in {schedule_time:.3f}s, "
            f"{pool_count} expiries in {expire_time:.3f}s"
        )


class TestWheelConfig:
    """Test wheel configuration functionality."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WheelConfig()
        assert config.second_slots == 60
        assert config.minute_slots == 60
        assert config.hour_slots == 24
        assert config.day_slots == 7

    def test_total_capacity_calculation(self):
        """Test total capacity calculation."""
        config = WheelConfig()
        total_seconds = config.total_capacity_seconds()

        expected = 60 + (60 * 60) + (24 * 3600) + (7 * 86400)
        assert total_seconds == expected

    def test_custom_config(self):
        """Test custom configuration."""
        config = WheelConfig(
            second_slots=30, minute_slots=30, hour_slots=12, day_slots=3
        )

        wheel = TimerWheel(config)
        assert wheel.config.second_slots == 30
        assert wheel.config.minute_slots == 30


class TestScheduledExpiry:
    """Test ScheduledExpiry data class."""

    def test_valid_expiry_creation(self):
        """Test creating valid expiry objects."""
        created = datetime.now()
        expires = created + timedelta(seconds=30)

        expiry = ScheduledExpiry("test_pool", expires, created)
        assert expiry.pool_id == "test_pool"
        assert expiry.expires_at == expires
        assert expiry.created_at == created

    def test_invalid_expiry_time_raises(self):
        """Test that expiry before creation raises error when appropriate."""
        created = datetime.now()
        expires = created - timedelta(seconds=10)  # Past expiry

        # Direct creation should not raise (validation moved to schedule)
        expiry = ScheduledExpiry("test_pool", expires, created)
        assert expiry.pool_id == "test_pool"

        # But scheduling with invalid times should fail
        wheel = TimerWheel()
        wheel.current_time = created
        result = wheel.schedule("test_pool", expires, created)
        assert result is False  # Should fail scheduling
