"""Tests for Phase 5: Overlap Detection and HLZ Generation."""

from datetime import UTC, datetime, timedelta

import pytest

from core.strategy.overlap import Interval, OverlapConfig, OverlapDetector, OverlapIndex
from core.strategy.pool_models import (
    HighLiquidityZone,
    HLZCreatedEvent,
    HLZExpiredEvent,
    HLZUpdatedEvent,
    LiquidityPool,
    PoolState,
    generate_hlz_id,
)


class TestHLZDataModels:
    """Test HLZ data structures and ID generation."""

    def test_generate_hlz_id_deterministic(self):
        """Test that HLZ ID generation is deterministic."""
        pool_ids1 = frozenset(["pool_1", "pool_2", "pool_3"])
        pool_ids2 = frozenset(["pool_3", "pool_1", "pool_2"])  # Different order

        id1 = generate_hlz_id(pool_ids1)
        id2 = generate_hlz_id(pool_ids2)

        assert id1 == id2
        assert id1.startswith("hlz_")
        assert len(id1) == 16  # "hlz_" + 12 hex chars

    def test_generate_hlz_id_unique(self):
        """Test that different pool sets generate different HLZ IDs."""
        pool_ids1 = frozenset(["pool_1", "pool_2"])
        pool_ids2 = frozenset(["pool_1", "pool_3"])

        id1 = generate_hlz_id(pool_ids1)
        id2 = generate_hlz_id(pool_ids2)

        assert id1 != id2

    def test_high_liquidity_zone_properties(self):
        """Test HLZ data structure properties."""
        timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        hlz = HighLiquidityZone(
            hlz_id="hlz_test123",
            side="bullish",
            top=1.2350,
            bottom=1.2300,
            strength=5.5,
            member_pool_ids=frozenset(["pool_1", "pool_2"]),
            created_at=timestamp,
            timeframes=frozenset(["H1", "H4"]),
        )

        assert hlz.mid_price == 1.2325
        assert abs(hlz.zone_height - 0.005) < 1e-10  # Handle floating point precision
        assert hlz.member_count == 2


class TestOverlapIndex:
    """Test interval tree implementation."""

    def test_add_and_query_intervals(self):
        """Test basic interval addition and overlap queries."""
        index = OverlapIndex()

        # Add bullish interval
        interval1 = Interval(
            start=1.2300,
            end=1.2350,
            pool_id="pool_1",
            side="bullish",
            timeframe="H1",
        )
        index.add_interval(interval1)

        # Add overlapping interval
        interval2 = Interval(
            start=1.2320,
            end=1.2370,
            pool_id="pool_2",
            side="bullish",
            timeframe="H4",
        )
        index.add_interval(interval2)

        # Query overlaps
        query_interval = Interval(
            start=1.2310,
            end=1.2360,
            pool_id="query",
            side="bullish",
            timeframe="H1",
        )

        result = index.query_overlaps(query_interval)

        assert len(result.overlapping_pools) == 2
        assert "pool_1" in result.overlapping_pools
        assert "pool_2" in result.overlapping_pools
        assert result.timeframes == {"H1", "H4"}

    def test_no_side_mixing_by_default(self):
        """Test that bullish and bearish intervals don't mix by default."""
        index = OverlapIndex(side_mixing=False)

        # Add bullish interval
        bullish_interval = Interval(
            start=1.2300,
            end=1.2350,
            pool_id="bullish_pool",
            side="bullish",
            timeframe="H1",
        )
        index.add_interval(bullish_interval)

        # Add bearish interval (overlapping price range)
        bearish_interval = Interval(
            start=1.2320,
            end=1.2370,
            pool_id="bearish_pool",
            side="bearish",
            timeframe="H4",
        )
        index.add_interval(bearish_interval)

        # Query with bullish interval - should only find bullish
        query_interval = Interval(
            start=1.2310,
            end=1.2360,
            pool_id="query",
            side="bullish",
            timeframe="H1",
        )

        result = index.query_overlaps(query_interval)

        assert len(result.overlapping_pools) == 1
        assert "bullish_pool" in result.overlapping_pools
        assert "bearish_pool" not in result.overlapping_pools

    def test_side_mixing_when_enabled(self):
        """Test that side mixing works when explicitly enabled."""
        index = OverlapIndex(side_mixing=True)

        # Add intervals of different sides
        bullish_interval = Interval(
            start=1.2300,
            end=1.2350,
            pool_id="bullish_pool",
            side="bullish",
            timeframe="H1",
        )
        index.add_interval(bullish_interval)

        bearish_interval = Interval(
            start=1.2320,
            end=1.2370,
            pool_id="bearish_pool",
            side="bearish",
            timeframe="H4",
        )
        index.add_interval(bearish_interval)

        # Query should find both when side mixing enabled
        query_interval = Interval(
            start=1.2310,
            end=1.2360,
            pool_id="query",
            side="bullish",
            timeframe="H1",
        )

        result = index.query_overlaps(query_interval)

        assert len(result.overlapping_pools) == 2
        assert result.sides == {"bullish", "bearish"}

    def test_remove_interval(self):
        """Test interval removal."""
        index = OverlapIndex()

        interval = Interval(
            start=1.2300,
            end=1.2350,
            pool_id="pool_1",
            side="bullish",
            timeframe="H1",
        )
        index.add_interval(interval)

        assert index.size() == 1

        # Remove interval
        removed = index.remove_interval("pool_1")
        assert removed is True
        assert index.size() == 0

        # Try to remove non-existent interval
        removed = index.remove_interval("nonexistent")
        assert removed is False


class TestOverlapDetector:
    """Test the main overlap detection logic."""

    def test_detector_initialization(self):
        """Test detector initialization with config."""
        config = OverlapConfig(
            min_members=3,
            min_strength=5.0,
            tf_weight={"H1": 1.0, "H4": 2.0},
        )

        detector = OverlapDetector(config)

        assert detector.config.min_members == 3
        assert detector.config.min_strength == 5.0
        assert detector.config.tf_weight["H4"] == 2.0

    def test_pool_creation_handling(self):
        """Test handling of pool creation events."""
        detector = OverlapDetector()
        timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        # Create a test pool
        pool = LiquidityPool(
            pool_id="test_pool_1",
            timeframe="H1",
            top=1.2350,
            bottom=1.2300,
            strength=0.8,
            state=PoolState.ACTIVE,
            created_at=timestamp,
            last_touched_at=None,
            expires_at=timestamp + timedelta(hours=2),
            side="bullish",
        )

        # Handle pool creation (should not create HLZ yet - need 2+ pools)
        events = detector.on_pool_created(pool, timestamp)

        assert len(events) == 0  # No HLZ events yet
        assert detector._overlap_index.size() == 1

    def test_pool_expiry_handling(self):
        """Test handling of pool expiry events."""
        detector = OverlapDetector()
        timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        # Create and add a pool
        pool = LiquidityPool(
            pool_id="test_pool_1",
            timeframe="H1",
            top=1.2350,
            bottom=1.2300,
            strength=0.8,
            state=PoolState.ACTIVE,
            created_at=timestamp,
            last_touched_at=None,
            expires_at=timestamp + timedelta(hours=2),
            side="bullish",
        )

        detector.on_pool_created(pool, timestamp)
        assert detector._overlap_index.size() == 1

        # Handle pool expiry
        events = detector.on_pool_expired("test_pool_1", timestamp)

        assert detector._overlap_index.size() == 0
        # No HLZ events expected since there was only one pool
        assert len(events) == 0

    def test_get_stats(self):
        """Test statistics collection."""
        detector = OverlapDetector()

        stats = detector.get_stats()

        assert "hlzs_created" in stats
        assert "hlzs_expired" in stats
        assert "pools_processed" in stats
        assert "overlaps_detected" in stats
        assert "active_hlzs" in stats
        assert "total_pools" in stats

        assert stats["pools_processed"] == 0
        assert stats["active_hlzs"] == 0


class TestOverlapConfig:
    """Test configuration handling."""

    def test_default_config(self):
        """Test default configuration values."""
        config = OverlapConfig()

        assert config.min_members == 2
        assert config.min_strength == 3.0
        assert config.tf_weight["H1"] == 1.0
        assert config.tf_weight["H4"] == 2.0
        assert config.tf_weight["D1"] == 3.0
        assert config.side_mixing is False

    def test_custom_config(self):
        """Test custom configuration values."""
        config = OverlapConfig(
            min_members=3,
            min_strength=5.0,
            tf_weight={"H1": 2.0, "H4": 4.0},
            side_mixing=True,
        )

        assert config.min_members == 3
        assert config.min_strength == 5.0
        assert config.tf_weight["H1"] == 2.0
        assert config.side_mixing is True


# Performance test placeholder
def test_overlap_detection_performance():
    """Test performance with large number of pools (placeholder)."""
    # This will be implemented in Step 5 when we have full integration
    pass


# Integration test placeholder
def test_three_pool_overlap_acceptance():
    """
    Acceptance test: 3 pools (H1 & H4 overlap) → expect HLZ strength = Σ weights.

    H1 (weight 1) + H4 (weight 2) bullish gap → HLZ strength 3
    """
    from core.strategy.pool_registry import PoolRegistry, PoolRegistryConfig

    # Create registry and configure detector with it
    registry_config = PoolRegistryConfig(enable_metrics=False)
    base_time = datetime(2025, 1, 1, 12, 0, 0)  # Define base_time first
    registry = PoolRegistry(registry_config, current_time=base_time)  # Set initial time

    config = OverlapConfig()
    detector = OverlapDetector(config, registry)

    # Create overlapping pools via registry

    # Add pools to registry first
    success1, pool_id1 = registry.add(
        timeframe="H1",
        top=1.1000,
        bottom=1.0950,
        strength=2.5,
        ttl=timedelta(hours=2),
        created_at=base_time,
        side="bullish",
    )
    assert success1

    success2, pool_id2 = registry.add(
        timeframe="H4",
        top=1.0990,  # Overlaps with pool1
        bottom=1.0960,  # Overlaps with pool1
        strength=1.8,
        ttl=timedelta(hours=8),
        created_at=base_time,
        side="bullish",
    )
    assert success2

    success3, pool_id3 = registry.add(
        timeframe="H1",
        top=1.0980,  # Overlaps with pool1 & pool2
        bottom=1.0970,  # Overlaps with pool1 & pool2
        strength=1.2,
        ttl=timedelta(hours=2),
        created_at=base_time,
        side="bullish",
    )
    assert success3

    # Get pool objects from registry
    pool1 = registry.get_pool(pool_id1)
    pool2 = registry.get_pool(pool_id2)
    pool3 = registry.get_pool(pool_id3)

    assert pool1 is not None
    assert pool2 is not None
    assert pool3 is not None

    # Process pools and check for HLZ creation
    events1 = detector.on_pool_created(pool1, base_time)
    events2 = detector.on_pool_created(pool2, base_time)
    events3 = detector.on_pool_created(pool3, base_time)

    # Should create HLZ when sufficient pools overlap
    all_events = events1 + events2 + events3
    hlz_created_events = [e for e in all_events if isinstance(e, HLZCreatedEvent)]

    assert len(hlz_created_events) >= 1, "Expected at least one HLZ to be created"

    # Find the HLZ with the highest strength (should be the one with all 3 pools)
    hlz = max(hlz_created_events, key=lambda e: e.hlz.strength).hlz

    # Check HLZ strength calculation: H1(1.0)*2.5 + H4(2.0)*1.8 + H1(1.0)*1.2 = 2.5 + 3.6 + 1.2 = 7.3
    expected_strength = 7.3  # TF-weighted sum
    assert abs(hlz.strength - expected_strength) < 0.01, (
        f"Expected strength ~{expected_strength}, got {hlz.strength}"
    )

    # Check that HLZ contains all overlapping pools
    assert hlz.member_count == 3, f"Expected 3 member pools, got {hlz.member_count}"

    # Verify overlap region is intersection of all pools
    assert hlz.mid_price >= 1.0970 and hlz.mid_price <= 1.0980, (
        f"HLZ mid_price {hlz.mid_price} not in overlap region"
    )


def test_overlap_detector_registry_integration():
    """Test that OverlapDetector integrates properly with PoolRegistry via listeners."""
    from core.strategy.pool_registry import PoolRegistry, PoolRegistryConfig

    # Create registry and detector
    registry_config = PoolRegistryConfig(enable_metrics=True)
    registry = PoolRegistry(registry_config)

    overlap_config = OverlapConfig()
    detector = OverlapDetector(overlap_config, registry)

    # Track events received by detector
    received_events = []

    def mock_on_pool_event(event):
        received_events.append(event)
        # Call the real detector methods based on event type
        if hasattr(event, "pool_id"):
            if event.event_type == "created":
                # Get the pool from registry
                pool = registry.get_pool(event.pool_id)
                if pool:
                    return detector.on_pool_created(pool, event.timestamp)
            elif event.event_type == "touched":
                return detector.on_pool_touched(
                    event.pool_id, event.touch_price, event.timestamp
                )
            elif event.event_type == "expired":
                return detector.on_pool_expired(event.pool_id, event.timestamp)
        return []

    # Register detector as listener
    registry.register_listener(mock_on_pool_event)

    # Add pools to registry - should trigger events
    success1, pool_id1 = registry.add(
        timeframe="H1", top=1.1000, bottom=1.0950, strength=2.5, ttl=timedelta(hours=2)
    )
    assert success1

    success2, pool_id2 = registry.add(
        timeframe="H4", top=1.0990, bottom=1.0960, strength=1.8, ttl=timedelta(hours=8)
    )
    assert success2

    # Verify events were received
    assert len(received_events) >= 2, (
        f"Expected at least 2 events, got {len(received_events)}"
    )

    # Check event types
    event_types = [e.event_type for e in received_events]
    assert "created" in event_types, "Expected PoolCreatedEvent"

    # Touch a pool - should trigger PoolTouchedEvent
    touch_success = registry.touch(pool_id1, 1.0975)
    assert touch_success

    # Verify touch event was received
    touch_events = [
        e for e in received_events if getattr(e, "event_type", None) == "touched"
    ]
    assert len(touch_events) >= 1, "Expected at least one PoolTouchedEvent"
