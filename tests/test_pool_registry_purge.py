"""
Tests for the pool registry purge_before functionality.
"""

from datetime import datetime, timedelta

from core.strategy.pool_models import PoolState
from core.strategy.pool_registry import PoolRegistry, PoolRegistryConfig
from core.strategy.ttl_wheel import WheelConfig


def test_purge_before_functionality():
    """Test the purge_before method for offline analysis cleanup."""
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    config = PoolRegistryConfig(grace_period_minutes=5)
    wheel_config = WheelConfig()
    registry = PoolRegistry(
        config=config, wheel_config=wheel_config, current_time=base_time
    )

    # Create pools at different times
    early_time = base_time
    later_time = base_time + timedelta(hours=1)

    # Create early pool
    success1, pool_id1 = registry.add(
        timeframe="H1",
        top=1.1000,
        bottom=1.0950,
        strength=0.8,
        ttl=timedelta(minutes=1),  # Short TTL for quick expiry
        created_at=early_time,
    )

    # Create later pool
    success2, pool_id2 = registry.add(
        timeframe="H1",
        top=1.2000,
        bottom=1.1950,
        strength=0.8,
        ttl=timedelta(minutes=1),  # Short TTL for quick expiry
        created_at=later_time,
    )

    assert success1 and success2
    assert registry.size() == 2

    # Expire both pools
    expire_time = later_time + timedelta(minutes=5)
    expired_events = registry.expire_due(expire_time)
    assert len(expired_events) == 2

    # Both pools should be in expired state and grace period
    pool1 = registry.get_pool(pool_id1)
    pool2 = registry.get_pool(pool_id2)
    assert pool1 is not None and pool1.state == PoolState.EXPIRED
    assert pool2 is not None and pool2.state == PoolState.EXPIRED
    assert pool_id1 in registry._grace_pools
    assert pool_id2 in registry._grace_pools

    # Purge pools created before the cutoff (should only affect pool1)
    cutoff_time = base_time + timedelta(minutes=30)
    purged_count = registry.purge_before(cutoff_time)

    assert purged_count == 1
    assert registry.get_pool(pool_id1) is None  # pool1 should be purged
    assert registry.get_pool(pool_id2) is not None  # pool2 should remain
    assert pool_id1 not in registry._grace_pools
    assert pool_id2 in registry._grace_pools


def test_purge_before_no_matching_pools():
    """Test purge_before when no pools match the criteria."""
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    config = PoolRegistryConfig()
    wheel_config = WheelConfig()
    registry = PoolRegistry(
        config=config, wheel_config=wheel_config, current_time=base_time
    )

    # Create and expire a pool
    success, pool_id = registry.add(
        timeframe="H1",
        top=1.1000,
        bottom=1.0950,
        strength=0.8,
        ttl=timedelta(minutes=1),
        created_at=base_time,
    )

    expire_time = base_time + timedelta(minutes=2)
    registry.expire_due(expire_time)

    # Purge with cutoff before pool creation
    cutoff_time = base_time - timedelta(hours=1)
    purged_count = registry.purge_before(cutoff_time)

    assert purged_count == 0
    assert registry.get_pool(pool_id) is not None  # Pool should still exist
