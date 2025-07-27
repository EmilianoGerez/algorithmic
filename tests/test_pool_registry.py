"""
Unit tests for Pool Registry with TTL management.

Tests cover:
- CRUD operations and performance
- Multi-timeframe isolation
- TTL expiry and grace periods
- Metrics collection
- Edge cases and error handling
"""

from datetime import datetime, timedelta

from core.strategy.pool_models import PoolState
from core.strategy.pool_registry import PoolRegistry, PoolRegistryConfig
from core.strategy.ttl_wheel import WheelConfig


class TestPoolRegistry:
    """Test suite for PoolRegistry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.base_time = datetime(2025, 1, 1, 12, 0, 0)
        self.config = PoolRegistryConfig(
            grace_period_minutes=5, enable_metrics=True, max_pools_per_tf=1000
        )
        self.wheel_config = WheelConfig()
        self.registry = PoolRegistry(
            config=self.config,
            wheel_config=self.wheel_config,
            current_time=self.base_time,
        )

    def test_basic_pool_creation(self):
        """Test basic pool creation and retrieval."""
        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(minutes=120),
        )

        assert success is True
        assert pool_id != ""
        assert self.registry.size() == 1

        # Retrieve the pool
        pool = self.registry.get_pool(pool_id)
        assert pool is not None
        assert pool.timeframe == "H1"
        assert pool.top == 1.1000
        assert pool.bottom == 1.0950
        assert pool.strength == 0.8
        assert pool.state == PoolState.ACTIVE

    def test_duplicate_prevention(self):
        """Test that duplicate pools are prevented."""
        # Create first pool
        success1, pool_id1 = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(minutes=120),
            created_at=self.base_time,
        )

        # Try to create identical pool
        success2, pool_id2 = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(minutes=120),
            created_at=self.base_time,  # Same creation time = same ID
        )

        assert success1 is True
        assert success2 is False
        assert pool_id1 == pool_id2
        assert self.registry.size() == 1

    def test_timeframe_capacity_limit(self):
        """Test timeframe capacity limits."""
        # Set low limit for testing
        self.registry.config.max_pools_per_tf = 3

        # Add pools up to limit
        for i in range(3):
            success, _ = self.registry.add(
                timeframe="H1",
                top=1.1000 + i * 0.001,  # Different prices for unique IDs
                bottom=1.0950 + i * 0.001,
                strength=0.8,
                ttl=timedelta(minutes=120),
            )
            assert success is True

        # Fourth pool should fail
        success, _ = self.registry.add(
            timeframe="H1",
            top=1.1030,
            bottom=1.0980,
            strength=0.8,
            ttl=timedelta(minutes=120),
        )
        assert success is False
        assert self.registry.size_by_timeframe("H1") == 3

    def test_pool_touching(self):
        """Test pool touch functionality."""
        # Create a pool
        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(minutes=120),
        )
        assert success is True

        # Touch the pool with valid price
        touch_success = self.registry.touch(pool_id, 1.0975)
        assert touch_success is True

        # Verify state change
        pool = self.registry.get_pool(pool_id)
        assert pool is not None
        assert pool.state == PoolState.TOUCHED
        assert pool.last_touched_at is not None
        assert self.registry.size_by_state(PoolState.ACTIVE) == 0
        assert self.registry.size_by_state(PoolState.TOUCHED) == 1

    def test_pool_touch_validation(self):
        """Test pool touch validation (price in zone)."""
        # Create a pool
        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(minutes=120),
            hit_tolerance=0.0001,  # 1 pip tolerance
        )

        # Valid touch (inside zone)
        assert self.registry.touch(pool_id, 1.0975) is True

        # Reset pool state for next test
        pool = self.registry.get_pool(pool_id)
        assert pool is not None
        reset_pool = pool.with_state(PoolState.ACTIVE, None)
        self.registry._pools[pool_id] = reset_pool
        self.registry._pools_by_state[PoolState.TOUCHED].discard(pool_id)
        self.registry._pools_by_state[PoolState.ACTIVE].add(pool_id)

        # Valid touch (with tolerance)
        assert (
            self.registry.touch(pool_id, 1.0949) is True
        )  # Just outside zone but within tolerance

        # Reset again
        assert pool is not None  # pool was already checked above
        reset_pool = pool.with_state(PoolState.ACTIVE, None)
        self.registry._pools[pool_id] = reset_pool
        self.registry._pools_by_state[PoolState.TOUCHED].discard(pool_id)
        self.registry._pools_by_state[PoolState.ACTIVE].add(pool_id)

        # Invalid touch (far outside zone)
        assert self.registry.touch(pool_id, 1.0900) is False

        # Pool should still be active
        pool = self.registry.get_pool(pool_id)
        assert pool is not None
        assert pool.state == PoolState.ACTIVE

    def test_ttl_expiry_1_second(self):
        """Test 1-second TTL expiry (acceptance criterion)."""
        # Create pool with 1-second TTL
        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(seconds=1),
            created_at=self.base_time,
        )
        assert success is True

        # Advance time by exactly 1 second
        expire_time = self.base_time + timedelta(seconds=1)
        expired_events = self.registry.expire_due(expire_time)

        # Should have one expiry event
        assert len(expired_events) == 1
        assert expired_events[0].pool_id == pool_id
        assert expired_events[0].event_type == "expired"

        # Pool should be in expired state
        pool = self.registry.get_pool(pool_id)
        assert pool is not None
        assert pool.state == PoolState.EXPIRED
        assert self.registry.size_by_state(PoolState.EXPIRED) == 1

    def test_multi_timeframe_isolation(self):
        """Test that expiring H1 pool doesn't affect H4 pool."""
        # Create H1 pool (short TTL)
        success1, h1_pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(minutes=5),
        )

        # Create H4 pool (longer TTL, overlapping price range)
        success2, h4_pool_id = self.registry.add(
            timeframe="H4",
            top=1.0990,  # Overlapping range
            bottom=1.0940,
            strength=0.9,
            ttl=timedelta(hours=6),
        )

        assert success1 is True
        assert success2 is True
        assert h1_pool_id != h4_pool_id

        # Advance time to expire H1 pool only
        expire_time = self.base_time + timedelta(minutes=10)
        expired_events = self.registry.expire_due(expire_time)

        # Only H1 pool should expire
        assert len(expired_events) == 1
        assert expired_events[0].pool_id == h1_pool_id

        # Verify H4 pool is still active
        h4_pool = self.registry.get_pool(h4_pool_id)
        assert h4_pool is not None
        assert h4_pool.state == PoolState.ACTIVE

        # Verify timeframe isolation
        h1_pools = self.registry.query_active(timeframe="H1")
        h4_pools = self.registry.query_active(timeframe="H4")
        assert len(h1_pools) == 0
        assert len(h4_pools) == 1

    def test_out_of_order_event_handling(self):
        """Test adding pool with created_at earlier than now."""
        # Create pool with past creation time
        past_time = self.base_time - timedelta(minutes=10)

        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(minutes=40),  # TTL from past creation time
            created_at=past_time,
        )

        assert success is True

        # Pool should be scheduled correctly despite out-of-order creation
        pool = self.registry.get_pool(pool_id)
        assert pool is not None
        assert pool.created_at == past_time
        assert pool.expires_at == past_time + timedelta(minutes=40)

        # Should not expire immediately
        current_expired = self.registry.expire_due(self.base_time)
        assert len(current_expired) == 0

    def test_grace_period_cleanup(self):
        """Test grace period and cleanup functionality."""
        # Create and expire a pool
        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(seconds=1),
        )

        # Expire the pool
        expire_time = self.base_time + timedelta(seconds=1)
        expired_events = self.registry.expire_due(expire_time)
        assert len(expired_events) == 1

        # Pool should still exist in expired state
        pool = self.registry.get_pool(pool_id)
        assert pool is not None
        assert pool.state == PoolState.EXPIRED

        # Advance past grace period + cleanup interval
        cleanup_time = expire_time + timedelta(
            minutes=70
        )  # Past 5-minute grace + 60-minute cleanup interval
        self.registry.expire_due(cleanup_time)

        # Pool should be cleaned up
        pool = self.registry.get_pool(pool_id)
        assert pool is None
        assert self.registry.size() == 0

    def test_query_active_pools(self):
        """Test querying active pools with filtering."""
        # Create pools in different timeframes
        pools_data = [
            ("H1", 1.1000, 1.0950),
            ("H1", 1.0900, 1.0850),
            ("H4", 1.1050, 1.1000),
            ("D1", 1.0800, 1.0750),
        ]

        created_pools = []
        for tf, top, bottom in pools_data:
            success, pool_id = self.registry.add(
                timeframe=tf,
                top=top,
                bottom=bottom,
                strength=0.8,
                ttl=timedelta(hours=1),
            )
            assert success is True
            created_pools.append((tf, pool_id))

        # Query all active pools
        all_active = self.registry.query_active()
        assert len(all_active) == 4

        # Query H1 pools only
        h1_pools = self.registry.query_active(timeframe="H1")
        assert len(h1_pools) == 2
        assert all(pool.timeframe == "H1" for pool in h1_pools)

        # Query H4 pools only
        h4_pools = self.registry.query_active(timeframe="H4")
        assert len(h4_pools) == 1
        assert h4_pools[0].timeframe == "H4"

        # Touch one H1 pool
        h1_pool_id = [pid for tf, pid in created_pools if tf == "H1"][0]
        self.registry.touch(h1_pool_id, 1.0975)

        # Query active H1 pools - should be one less
        h1_active = self.registry.query_active(timeframe="H1")
        assert len(h1_active) == 1

    def test_remove_pool(self):
        """Test manual pool removal."""
        # Create a pool
        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(minutes=120),
        )
        assert success is True
        assert self.registry.size() == 1

        # Remove the pool
        removed = self.registry.remove(pool_id)
        assert removed is True
        assert self.registry.size() == 0
        assert self.registry.get_pool(pool_id) is None

        # Second removal should fail
        removed_again = self.registry.remove(pool_id)
        assert removed_again is False

    def test_metrics_collection(self):
        """Test Prometheus-style metrics collection."""
        # Initial metrics
        initial_metrics = self.registry.get_metrics()
        assert "prometheus" in initial_metrics
        prometheus = initial_metrics["prometheus"]
        assert prometheus["pool_registry_pools_created_total"] == 0

        # Create some pools
        for i in range(3):
            success, pool_id = self.registry.add(
                timeframe="H1",
                top=1.1000 + i * 0.001,
                bottom=1.0950 + i * 0.001,
                strength=0.8,
                ttl=timedelta(minutes=120),
            )
            assert success is True

        # Touch one pool
        pools = self.registry.query_active()
        self.registry.touch(pools[0].pool_id, 1.0975)

        # Check updated metrics
        updated_metrics = self.registry.get_metrics()
        prometheus = updated_metrics["prometheus"]
        assert prometheus["pool_registry_pools_created_total"] == 3
        assert prometheus["pool_registry_pools_touched_total"] == 1
        assert prometheus["pool_registry_active_pools"] == 2
        assert prometheus["pool_registry_touched_pools"] == 1
        assert prometheus["pool_registry_total_pools"] == 3

    def test_crud_performance_10k_pools(self):
        """Test CRUD performance with 10k pools (acceptance criterion)."""
        import time

        # Increase capacity for this test
        self.registry.config.max_pools_per_tf = 50000  # Much higher capacity

        # Reconfigure the TTL wheel for high capacity
        self.registry._ttl_wheel.config.max_items_per_slot = 10000

        pool_count = 10000

        # Create 10k pools
        start_time = time.time()
        created_pools = []

        for i in range(pool_count):
            success, pool_id = self.registry.add(
                timeframe="H1",
                top=10.0000
                + i * 1.0,  # Start from 10.0 with 1.0 increments (like phase4 test)
                bottom=9.5000 + i * 1.0,
                strength=0.8,
                ttl=timedelta(minutes=120),
                created_at=self.base_time,  # Use consistent created_at time
            )
            if not success:
                print(f"Failed to create pool at index {i}")
                print(f"Registry size: {self.registry.size()}")
                print(f"Max pools per tf: {self.registry.config.max_pools_per_tf}")
                break
            assert success is True
            created_pools.append(pool_id)

        create_time = time.time() - start_time

        # Update (touch) pools
        start_time = time.time()
        for i in range(
            0, min(len(created_pools), pool_count), 10
        ):  # Touch every 10th pool (safe indexing)
            pool_id = created_pools[i]
            # Touch with price within range [9.5 + i, 10.0 + i]
            touch_price = 9.75 + i * 1.0  # Midpoint
            self.registry.touch(pool_id, touch_price)

        update_time = time.time() - start_time

        # Expire all pools
        start_time = time.time()
        expire_time = self.base_time + timedelta(minutes=130)
        expired_events = self.registry.expire_due(expire_time)
        expire_time_elapsed = time.time() - start_time

        total_time = create_time + update_time + expire_time_elapsed

        # Performance assertions - more lenient for CI environments
        import os

        is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
        time_limit = (
            1.0 if is_ci else 0.3
        )  # 1 second for CI, 300ms for local (more realistic)

        assert total_time < time_limit, (
            f"Total time {total_time:.3f}s exceeds {time_limit}s limit"
        )
        assert len(created_pools) == pool_count  # Make sure all pools were created
        assert len(expired_events) == pool_count

        print(
            f"Performance: {pool_count} pools - "
            f"Create: {create_time:.3f}s, Update: {update_time:.3f}s, "
            f"Expire: {expire_time_elapsed:.3f}s, Total: {total_time:.3f}s"
        )

    def test_pool_id_generation_uniqueness(self):
        """Test that pool ID generation is deterministic and unique."""
        from core.strategy.pool_models import generate_pool_id

        # Same inputs should generate same ID
        id1 = generate_pool_id("H1", self.base_time, 1.1000, 1.0950)
        id2 = generate_pool_id("H1", self.base_time, 1.1000, 1.0950)
        assert id1 == id2

        # Different inputs should generate different IDs
        id3 = generate_pool_id("H1", self.base_time, 1.1001, 1.0950)  # Different top
        id4 = generate_pool_id("H4", self.base_time, 1.1000, 1.0950)  # Different TF
        id5 = generate_pool_id(
            "H1", self.base_time + timedelta(seconds=1), 1.1000, 1.0950
        )  # Different time

        assert id1 != id3
        assert id1 != id4
        assert id1 != id5

        # Check ID format
        assert id1.startswith("H1_")
        assert "_" in id1[3:]  # Should have timestamp and hash parts

    def test_edge_case_zero_ttl(self):
        """Test edge case of zero TTL."""
        # Pool with zero TTL should fail to schedule
        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.1000,
            bottom=1.0950,
            strength=0.8,
            ttl=timedelta(seconds=0),
        )

        # Should fail because expiry time equals creation time
        assert success is False
        assert self.registry.size() == 0

    def test_edge_case_invalid_price_zone(self):
        """Test pools with invalid price zones."""
        # Create pool where top < bottom (inverted zone)
        success, pool_id = self.registry.add(
            timeframe="H1",
            top=1.0950,  # Lower than bottom
            bottom=1.1000,
            strength=0.8,
            ttl=timedelta(minutes=120),
        )

        # Should still create (pool handles this internally)
        assert success is True

        # Test touch with inverted zone
        pool = self.registry.get_pool(pool_id)
        assert pool is not None
        assert pool.is_price_in_zone(1.0975) is True  # Should work with min/max logic


class TestPoolRegistryConfig:
    """Test pool registry configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PoolRegistryConfig()
        assert config.grace_period == timedelta(minutes=5)
        assert config.enable_metrics is True
        assert config.max_pools_per_tf == 10000

    def test_custom_config(self):
        """Test custom configuration."""
        config = PoolRegistryConfig(
            grace_period_minutes=10, enable_metrics=False, max_pools_per_tf=5000
        )

        registry = PoolRegistry(config=config)
        assert registry.config.grace_period == timedelta(minutes=10)
        assert registry.config.enable_metrics is False
        assert registry.metrics is None  # Disabled


class TestPoolRegistryMetrics:
    """Test metrics collection functionality."""

    def test_metrics_initialization(self):
        """Test metrics start at zero."""
        from core.strategy.pool_registry import PoolRegistryMetrics

        metrics = PoolRegistryMetrics()
        assert metrics.pools_created == 0
        assert metrics.pools_touched == 0
        assert metrics.pools_expired == 0
        assert metrics.get_total_pools() == 0

    def test_metrics_recording(self):
        """Test that metrics are recorded correctly."""
        from core.strategy.pool_registry import PoolRegistryMetrics

        metrics = PoolRegistryMetrics()

        # Record some events
        metrics.record_pool_created("H1")
        metrics.record_pool_created("H4")
        metrics.record_pool_touched("H1")
        metrics.record_pool_expired("H1", PoolState.TOUCHED)

        # Check counters
        assert metrics.pools_created == 2
        assert metrics.pools_touched == 1
        assert metrics.pools_expired == 1

        # Check per-timeframe tracking
        assert metrics.active_pools_by_tf["H4"] == 1  # H4 still active
        assert metrics.touched_pools_by_tf["H1"] == 0  # H1 was expired
        assert metrics.expired_pools_by_tf["H1"] == 1  # H1 now expired

    def test_prometheus_metrics_format(self):
        """Test Prometheus metrics format."""
        from core.strategy.pool_registry import PoolRegistryMetrics

        metrics = PoolRegistryMetrics()
        metrics.record_pool_created("H1")
        metrics.record_pool_created("H4")

        prometheus = metrics.get_prometheus_metrics()

        # Check required metrics exist
        assert "pool_registry_pools_created_total" in prometheus
        assert "pool_registry_active_pools" in prometheus
        assert "pool_registry_total_pools" in prometheus
        assert "pool_registry_active_pools_tf_h1" in prometheus
        assert "pool_registry_active_pools_tf_h4" in prometheus

        # Check values
        assert prometheus["pool_registry_pools_created_total"] == 2
        assert prometheus["pool_registry_active_pools"] == 2
