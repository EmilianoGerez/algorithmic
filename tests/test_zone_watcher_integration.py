"""
Integration tests for ZoneWatcher + FSM interaction.

Tests the full flow: pool/HLZ events → zone tracking → price entry →
candidate spawn → FSM processing → signal emission.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from core.entities import Candle
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.pool_models import (
    HighLiquidityZone,
    HLZCreatedEvent,
    LiquidityPool,
    PoolCreatedEvent,
    PoolState,
)
from core.strategy.signal_candidate import CandidateConfig, SignalCandidateFSM
from core.strategy.signal_models import (
    CandidateState,
    SignalDirection,
    ZoneType,
)
from core.strategy.zone_watcher import ZoneWatcher, ZoneWatcherConfig


class TestZoneWatcherIntegration:
    """Integration tests for ZoneWatcher functionality."""

    @pytest.fixture
    def base_time(self):
        """Base timestamp for tests."""
        return datetime(2024, 1, 1, 12, 0)

    @pytest.fixture
    def zone_watcher(self):
        """Create ZoneWatcher with test configuration."""
        zone_config = ZoneWatcherConfig(
            price_tolerance=0.5,
            confirm_closure=False,
            min_strength=1.0,
            max_active_zones=100,
        )

        candidate_config = CandidateConfig(
            expiry_minutes=120,
            ema_alignment=True,
            volume_multiple=1.2,
            killzone_start="12:00",
            killzone_end="14:05",
            regime_allowed=["bull", "neutral"],
        )

        return ZoneWatcher(zone_config, candidate_config)

    @pytest.fixture
    def sample_pool(self, base_time):
        """Create sample liquidity pool."""
        return LiquidityPool(
            pool_id="H1_test_pool_001",
            timeframe="H1",
            top=102.0,
            bottom=98.0,
            strength=2.0,
            state=PoolState.ACTIVE,
            created_at=base_time,
            last_touched_at=None,
            expires_at=base_time + timedelta(hours=4),
        )

    @pytest.fixture
    def sample_hlz(self, base_time):
        """Create sample HLZ."""
        return HighLiquidityZone(
            hlz_id="hlz_abc123def456",
            side="bullish",
            top=105.0,
            bottom=95.0,
            strength=5.0,
            member_pool_ids=frozenset(["H1_pool_1", "H4_pool_2"]),
            created_at=base_time,
            timeframes=frozenset(["H1", "H4"]),
        )

    def test_pool_event_adds_zone_tracking(self, zone_watcher, sample_pool, base_time):
        """Test that pool creation event adds zone to tracking."""
        # Create pool event
        pool_event = PoolCreatedEvent(
            pool_id=sample_pool.pool_id,
            timestamp=base_time,
            pool=sample_pool,
        )

        # Process event
        zone_watcher.on_pool_event(pool_event)

        # Verify zone is tracked
        active_zones = zone_watcher.get_active_zones()
        assert sample_pool.pool_id in active_zones

        zone_meta = active_zones[sample_pool.pool_id]
        assert zone_meta.zone_type == ZoneType.POOL
        assert zone_meta.strength == 2.0
        assert zone_meta.timeframe == "H1"

    def test_hlz_event_adds_zone_tracking(self, zone_watcher, sample_hlz, base_time):
        """Test that HLZ creation event adds zone to tracking."""
        # Create HLZ event
        hlz_event = HLZCreatedEvent(
            hlz_id=sample_hlz.hlz_id,
            timestamp=base_time,
            hlz=sample_hlz,
        )

        # Process event
        zone_watcher.on_hlz_event(hlz_event)

        # Verify zone is tracked
        active_zones = zone_watcher.get_active_zones()
        assert sample_hlz.hlz_id in active_zones

        zone_meta = active_zones[sample_hlz.hlz_id]
        assert zone_meta.zone_type == ZoneType.HLZ
        assert zone_meta.strength == 5.0
        assert zone_meta.side == "bullish"

    def test_price_entry_detection(self, zone_watcher, sample_pool, base_time):
        """Test zone entry detection on price update."""
        # Add pool to tracking
        pool_event = PoolCreatedEvent(
            pool_id=sample_pool.pool_id,
            timestamp=base_time,
            pool=sample_pool,
        )
        zone_watcher.on_pool_event(pool_event)

        # Create candle that enters the zone (98-102 range)
        entry_candle = Candle(
            ts=base_time + timedelta(minutes=5),
            open=105.0,
            high=105.0,
            low=97.0,
            close=100.0,  # Inside zone
            volume=1500,
        )

        # Process price update
        zone_events = zone_watcher.on_price_update(entry_candle)

        # Should detect zone entry
        assert len(zone_events) == 1
        event = zone_events[0]
        assert event.zone_id == sample_pool.pool_id
        assert event.zone_type == ZoneType.POOL
        assert event.entry_price == 100.0

    def test_candidate_spawn_from_zone_entry(
        self, zone_watcher, sample_pool, base_time
    ):
        """Test candidate spawning from zone entry event."""
        # Add pool and detect entry
        pool_event = PoolCreatedEvent(
            pool_id=sample_pool.pool_id,
            timestamp=base_time,
            pool=sample_pool,
        )
        zone_watcher.on_pool_event(pool_event)

        entry_candle = Candle(
            ts=base_time + timedelta(minutes=5),
            open=105.0,
            high=105.0,
            low=97.0,
            close=100.0,
            volume=1500,
        )

        zone_events = zone_watcher.on_price_update(entry_candle)
        zone_entry = zone_events[0]

        # Spawn candidate
        candidate = zone_watcher.spawn_candidate(zone_entry, entry_candle.ts)

        # Verify candidate properties
        assert candidate.zone_id == sample_pool.pool_id
        assert candidate.zone_type == ZoneType.POOL
        assert candidate.direction == SignalDirection.LONG  # Inferred from "bullish"
        assert candidate.entry_price == 100.0
        assert candidate.state == CandidateState.WAIT_EMA


class TestFullSignalGenerationFlow:
    """Test complete flow from zone entry to signal emission."""

    @pytest.fixture
    def fsm(self):
        """Create FSM for testing."""
        config = CandidateConfig(
            expiry_minutes=120,
            ema_alignment=True,
            volume_multiple=1.2,
            killzone_start="12:00",
            killzone_end="14:05",
            regime_allowed=["bull", "neutral"],
        )
        return SignalCandidateFSM(config)

    @pytest.fixture
    def good_snapshot(self):
        """Create snapshot that passes all filters."""
        snapshot = Mock(spec=IndicatorSnapshot)
        snapshot.ema21 = 102.0
        snapshot.ema50 = 101.0
        snapshot.volume_sma = 1000.0
        snapshot.regime = "bull"
        return snapshot

    def test_complete_signal_generation_flow(self, fsm, good_snapshot):
        """Test complete flow: zone entry → candidate → FSM → signal."""
        base_time = datetime(2024, 1, 1, 12, 0)

        # Step 1: Create candidate (simulating zone entry)
        candidate = fsm.create_candidate(
            zone_id="H1_test_zone_001",
            zone_type="pool",
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=3.0,
            timestamp=base_time,
        )

        assert candidate.state == CandidateState.WAIT_EMA

        # Step 2: Process candle with good EMA alignment
        good_candle = Candle(
            ts=base_time + timedelta(minutes=1),
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,  # Above EMA21
            volume=1500,  # Above volume threshold
        )

        # First processing: WAIT_EMA → FILTERS
        result1 = fsm.process(candidate, good_candle, good_snapshot)
        assert result1.updated_candidate.state == CandidateState.FILTERS
        assert result1.signal is None

        # Step 3: Process next candle in FILTERS state
        next_candle = Candle(
            ts=base_time + timedelta(minutes=2),
            open=103.0,
            high=106.0,
            low=102.0,
            close=105.0,
            volume=1400,
        )

        # Second processing: FILTERS → READY (with signal)
        result2 = fsm.process(result1.updated_candidate, next_candle, good_snapshot)
        assert result2.updated_candidate.state == CandidateState.READY
        assert result2.signal is not None

        # Verify signal properties
        signal = result2.signal
        assert signal.zone_id == "H1_test_zone_001"
        assert signal.direction == SignalDirection.LONG
        assert signal.current_price == 105.0
        assert signal.strength == 3.0
        assert signal.timeframe == "H1"  # Extracted from zone_id

    def test_signal_generation_with_bad_filters(self, fsm, good_snapshot):
        """Test that bad filters prevent signal generation."""
        base_time = datetime(2024, 1, 1, 12, 0)

        candidate = fsm.create_candidate(
            zone_id="H1_test_zone_001",
            zone_type="pool",
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=3.0,
            timestamp=base_time,
        )

        # Move to FILTERS state first
        good_candle = Candle(
            ts=base_time + timedelta(minutes=1),
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1500,
        )

        result1 = fsm.process(candidate, good_candle, good_snapshot)
        candidate_in_filters = result1.updated_candidate

        # Create candle with bad volume
        # Try with bad volume - should not progress to READY
        bad_volume_candle = Candle(
            ts=base_time + timedelta(minutes=2),
            open=103.0,
            high=106.0,
            low=102.0,
            close=105.0,
            volume=500,  # Below threshold
        )

        # Should stay in FILTERS, no signal
        result2 = fsm.process(candidate_in_filters, bad_volume_candle, good_snapshot)
        assert result2.updated_candidate.state == CandidateState.FILTERS
        assert result2.signal is None

    def test_candidate_expiry_prevents_signal(self, fsm, good_snapshot):
        """Test that expired candidates don't generate signals."""
        base_time = datetime(2024, 1, 1, 12, 0)

        # Create candidate with short expiry
        candidate = fsm.create_candidate(
            zone_id="H1_test_zone_001",
            zone_type="pool",
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=3.0,
            timestamp=base_time,
        )

        # Create candle after expiry time
        expired_candle = Candle(
            ts=base_time + timedelta(hours=3),  # After 2-hour expiry
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,
            volume=1500,
        )

        # Should expire immediately
        result = fsm.process(candidate, expired_candle, good_snapshot)
        assert result.updated_candidate.state == CandidateState.EXPIRED
        assert result.expired
        assert result.signal is None


class TestZoneWatcherStats:
    """Test ZoneWatcher statistics and performance tracking."""

    def test_statistics_tracking(self):
        """Test that statistics are properly tracked."""
        zone_watcher = ZoneWatcher()

        # Initial stats
        stats = zone_watcher.get_stats()
        assert stats["zones_tracked"] == 0
        assert stats["zone_entries"] == 0
        assert stats["candidates_spawned"] == 0
        assert stats["active_zones"] == 0

        # Add a zone
        base_time = datetime.now()
        pool = LiquidityPool(
            pool_id="test_pool",
            timeframe="H1",
            top=102.0,
            bottom=98.0,
            strength=2.0,
            state=PoolState.ACTIVE,
            created_at=base_time,
            last_touched_at=None,
            expires_at=base_time + timedelta(hours=4),
        )

        pool_event = PoolCreatedEvent(
            pool_id=pool.pool_id,
            timestamp=base_time,
            pool=pool,
        )

        zone_watcher.on_pool_event(pool_event)

        # Check updated stats
        stats = zone_watcher.get_stats()
        assert stats["zones_tracked"] == 1
        assert stats["active_zones"] == 1
