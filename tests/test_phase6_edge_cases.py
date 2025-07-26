"""
Phase 6 Edge Case Tests: Advanced scenarios for ZoneWatcher + FSM.

Tests complex real-world scenarios that could cause incorrect behavior:
- Multiple zone entries without duplicate candidates
- Regime changes during FSM processing
- Candidate expiry before signal generation
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from core.entities import Candle
from core.indicators.regime import Regime
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.pool_models import LiquidityPool, PoolCreatedEvent, PoolState
from core.strategy.signal_candidate import CandidateConfig, SignalCandidateFSM
from core.strategy.signal_models import CandidateState, SignalDirection
from core.strategy.zone_watcher import ZoneWatcher, ZoneWatcherConfig


class TestPhase6EdgeCases:
    """Edge case tests for Phase 6 ZoneWatcher + FSM integration."""

    @pytest.fixture
    def zone_config(self) -> ZoneWatcherConfig:
        """Basic zone watcher configuration."""
        return ZoneWatcherConfig(
            price_tolerance=0.1,
            min_strength=1.0,
            max_active_zones=100,
        )

    @pytest.fixture
    def candidate_config(self) -> CandidateConfig:
        """Basic candidate configuration."""
        return CandidateConfig(
            expiry_minutes=120,  # 2 hours default
            ema_alignment=True,
            volume_multiple=1.2,
            killzone_start="12:00",
            killzone_end="14:00",
            regime_allowed=["bull", "neutral"],
        )

    @pytest.fixture
    def short_expiry_config(self) -> CandidateConfig:
        """Candidate config with short expiry for testing."""
        return CandidateConfig(
            expiry_minutes=30,  # 30 minutes for quick expiry
            ema_alignment=True,
            volume_multiple=1.2,
            killzone_start="12:00",
            killzone_end="14:00",
            regime_allowed=["bull", "neutral"],
        )

    @pytest.fixture
    def base_time(self) -> datetime:
        """Base time for tests."""
        return datetime(2024, 1, 1, 13, 0)  # In killzone

    @pytest.fixture
    def sample_pool(self, base_time: datetime) -> LiquidityPool:
        """Sample liquidity pool for testing."""
        return LiquidityPool(
            pool_id="H1_edge_test_pool",
            timeframe="H1",
            top=102.0,
            bottom=98.0,
            strength=2.5,
            state=PoolState.ACTIVE,
            created_at=base_time,
            last_touched_at=None,
            expires_at=base_time + timedelta(hours=4),
            hit_tolerance=0.0,
        )

    def test_multiple_entries_same_zone_single_candidate(
        self,
        zone_config: ZoneWatcherConfig,
        candidate_config: CandidateConfig,
        base_time: datetime,
        sample_pool: LiquidityPool,
    ) -> None:
        """
        Test: Multiple consecutive bars entering same zone should spawn only ONE candidate.

        Why: Prevents candidate spam when price oscillates within zone bounds.
        """
        zone_watcher = ZoneWatcher(zone_config, candidate_config)

        # Add pool to tracking
        pool_event = PoolCreatedEvent(
            pool_id=sample_pool.pool_id,
            timestamp=base_time,
            pool=sample_pool,
        )
        zone_watcher.on_pool_event(pool_event)

        all_zone_events = []

        # Create 5 consecutive bars ALL inside the zone (98-102)
        for i in range(5):
            entry_candle = Candle(
                ts=base_time + timedelta(minutes=i),
                open=99.0,
                high=101.0,
                low=99.0,
                close=100.0,  # Always inside zone
                volume=1500,
            )

            zone_events = zone_watcher.on_price_update(entry_candle)
            all_zone_events.extend(zone_events)

        # Should only have ONE zone entry event, not 5
        assert len(all_zone_events) == 1, (
            f"Expected 1 zone entry, got {len(all_zone_events)}"
        )

        # Verify the single event properties
        zone_entry = all_zone_events[0]
        assert zone_entry.zone_id == sample_pool.pool_id
        assert zone_entry.entry_price == 100.0

        # Verify ZoneWatcher stats show only 1 entry
        stats = zone_watcher.get_stats()
        assert stats["zone_entries"] == 1
        assert stats["zones_tracked"] == 1

    def test_regime_flip_prevents_filters_to_ready_transition(
        self,
        zone_config: ZoneWatcherConfig,
        candidate_config: CandidateConfig,
        base_time: datetime,
    ) -> None:
        """
        Test: Regime change should prevent FILTERS → READY transition.

        Why: Ensures regime guard prevents signals during unfavorable market conditions.
        """
        fsm = SignalCandidateFSM(candidate_config)

        # Create candidate in WAIT_EMA state
        candidate = fsm.create_candidate(
            zone_id="H1_regime_test_zone",
            zone_type="pool",
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=3.0,
            timestamp=base_time,
        )

        assert candidate.state == CandidateState.WAIT_EMA

        # Create candle with GOOD EMA alignment
        good_ema_candle = Candle(
            ts=base_time + timedelta(minutes=1),
            open=100.0,
            high=105.0,
            low=95.0,
            close=103.0,  # Above EMA21
            volume=1500,
        )

        # Create snapshot with good EMA conditions
        good_snapshot = IndicatorSnapshot(
            timestamp=good_ema_candle.ts,
            ema21=102.0,  # Below close (good for long)
            ema50=101.0,  # Below EMA21 (good for long)
            atr=1.5,
            volume_sma=1000.0,
            regime=Regime.BULL,  # Good regime initially
            regime_with_slope=Regime.BULL,
            current_volume=good_ema_candle.volume,
            current_close=good_ema_candle.close,
        )

        # First processing: WAIT_EMA → FILTERS (should succeed)
        result1 = fsm.process(candidate, good_ema_candle, good_snapshot)
        assert result1.updated_candidate.state == CandidateState.FILTERS
        assert result1.signal is None

        # Now create snapshot with BAD regime for second candle
        bad_regime_candle = Candle(
            ts=base_time + timedelta(minutes=2),
            open=103.0,
            high=106.0,
            low=102.0,
            close=104.0,
            volume=1600,  # Good volume
        )

        bad_regime_snapshot = IndicatorSnapshot(
            timestamp=bad_regime_candle.ts,
            ema21=102.5,
            ema50=101.5,
            atr=1.5,
            volume_sma=1000.0,
            regime=Regime.BEAR,  # BAD - not in allowed regimes ["bull", "neutral"]
            regime_with_slope=Regime.BEAR,
            current_volume=bad_regime_candle.volume,
            current_close=bad_regime_candle.close,
        )

        # Process with good conditions except bad regime
        result2 = fsm.process(
            result1.updated_candidate, bad_regime_candle, bad_regime_snapshot
        )

        # Should stay in FILTERS due to regime guard failure
        assert result2.updated_candidate.state == CandidateState.FILTERS
        assert result2.signal is None

        # Verify multiple attempts with bad regime still fail
        for i in range(3):
            next_candle = Candle(
                ts=base_time + timedelta(minutes=3 + i),
                open=104.0,
                high=107.0,
                low=103.0,
                close=105.0,
                volume=1700,
            )

            # Keep bad regime
            bad_snapshot = IndicatorSnapshot(
                timestamp=next_candle.ts,
                ema21=103.0,
                ema50=102.0,
                atr=1.5,
                volume_sma=1000.0,
                regime=Regime.BEAR,  # Still bad
                regime_with_slope=Regime.BEAR,
                current_volume=next_candle.volume,
                current_close=next_candle.close,
            )

            result = fsm.process(result2.updated_candidate, next_candle, bad_snapshot)
            assert result.updated_candidate.state == CandidateState.FILTERS
            assert result.signal is None

    def test_expiry_before_filters_pass_no_signal(
        self,
        zone_config: ZoneWatcherConfig,
        short_expiry_config: CandidateConfig,
        base_time: datetime,
    ) -> None:
        """
        Test: Candidate expiry before filters pass should result in EXPIRED state with no signal.

        Why: Prevents stale signals from old zone entries.
        """
        fsm = SignalCandidateFSM(short_expiry_config)  # 30-minute expiry

        # Create candidate
        candidate = fsm.create_candidate(
            zone_id="H1_expiry_test_zone",
            zone_type="pool",
            direction=SignalDirection.LONG,
            entry_price=100.0,
            strength=2.0,
            timestamp=base_time,
        )

        assert candidate.state == CandidateState.WAIT_EMA

        # Process several bars with good conditions but keep one filter failing
        for minute_offset in range(10, 35, 5):  # 10, 15, 20, 25, 30 minutes
            test_candle = Candle(
                ts=base_time + timedelta(minutes=minute_offset),
                open=100.0,
                high=105.0,
                low=95.0,
                close=103.0,
                volume=1500,
            )

            # Good EMA, good volume, good killzone, but BAD regime until expiry
            snapshot = IndicatorSnapshot(
                timestamp=test_candle.ts,
                ema21=102.0,  # Good EMA alignment
                ema50=101.0,
                atr=1.5,
                volume_sma=1000.0,
                regime=Regime.BEAR,  # Keep regime bad to prevent progression
                regime_with_slope=Regime.BEAR,
                current_volume=test_candle.volume,
                current_close=test_candle.close,
            )

            result = fsm.process(candidate, test_candle, snapshot)
            candidate = result.updated_candidate

            # Should move WAIT_EMA → FILTERS due to good EMA,
            # then stay in FILTERS due to bad regime
            if minute_offset < 30:  # Before expiry
                expected_state = (
                    CandidateState.FILTERS
                    if minute_offset >= 10
                    else CandidateState.WAIT_EMA
                )
                assert candidate.state == expected_state
                assert result.signal is None
                assert not result.expired
            else:  # At or after expiry (minute 30+)
                assert candidate.state == CandidateState.EXPIRED
                assert result.signal is None
                assert result.expired

        # Verify final state is EXPIRED with no signal emitted
        assert candidate.state == CandidateState.EXPIRED

    def test_zone_touch_tolerance_boundary_conditions(
        self,
        zone_config: ZoneWatcherConfig,
        candidate_config: CandidateConfig,
        base_time: datetime,
        sample_pool: LiquidityPool,
    ) -> None:
        """
        Test: Zone touch detection with price tolerance boundary conditions.

        Why: Ensures proper zone entry detection at exact boundaries.
        """
        zone_watcher = ZoneWatcher(zone_config, candidate_config)

        # Add pool to tracking (zone: 98.0 - 102.0, tolerance: 0.1)
        pool_event = PoolCreatedEvent(
            pool_id=sample_pool.pool_id,
            timestamp=base_time,
            pool=sample_pool,
        )
        zone_watcher.on_pool_event(pool_event)

        # Test cases: [price, should_trigger_entry]
        test_cases = [
            (97.85, False),  # Just outside tolerance (98.0 - 0.1 = 97.9)
            (97.9, True),  # Exactly at tolerance boundary (bottom - tolerance)
            (97.95, True),  # Just inside tolerance
            (98.0, True),  # Exactly at zone bottom
            (100.0, True),  # Inside zone
            (102.0, True),  # Exactly at zone top
            (102.05, True),  # Just inside tolerance
            (102.1, True),  # Exactly at tolerance boundary (top + tolerance)
            (102.15, False),  # Just outside tolerance (102.0 + 0.1 = 102.1)
        ]

        zone_entries = 0

        for i, (price, should_trigger) in enumerate(test_cases):
            test_candle = Candle(
                ts=base_time + timedelta(minutes=i),
                open=price,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=1500,
            )

            zone_events = zone_watcher.on_price_update(test_candle)

            if should_trigger and zone_entries == 0:
                # First valid entry should trigger
                assert len(zone_events) == 1, f"Price {price} should trigger zone entry"
                zone_entries += 1
            elif should_trigger and zone_entries > 0:
                # Subsequent entries to same zone should not trigger new events
                assert len(zone_events) == 0, (
                    f"Price {price} should not trigger duplicate zone entry"
                )
            else:
                # Outside tolerance should not trigger
                assert len(zone_events) == 0, (
                    f"Price {price} should not trigger zone entry"
                )

        # Verify only one zone entry was detected
        stats = zone_watcher.get_stats()
        assert stats["zone_entries"] == 1

    def test_concurrent_zone_entries_different_zones(
        self,
        zone_config: ZoneWatcherConfig,
        candidate_config: CandidateConfig,
        base_time: datetime,
    ) -> None:
        """
        Test: Multiple zone entries in different zones should spawn separate candidates.

        Why: Ensures ZoneWatcher can handle multiple active zones simultaneously.
        """
        zone_watcher = ZoneWatcher(zone_config, candidate_config)

        # Create two different pools
        pool1 = LiquidityPool(
            pool_id="H1_zone1_test",
            timeframe="H1",
            top=102.0,
            bottom=98.0,
            strength=2.0,
            state=PoolState.ACTIVE,
            created_at=base_time,
            last_touched_at=None,
            expires_at=base_time + timedelta(hours=4),
            hit_tolerance=0.0,
        )

        pool2 = LiquidityPool(
            pool_id="H1_zone2_test",
            timeframe="H1",
            top=110.0,
            bottom=106.0,
            strength=3.0,
            state=PoolState.ACTIVE,
            created_at=base_time,
            last_touched_at=None,
            expires_at=base_time + timedelta(hours=4),
            hit_tolerance=0.0,
        )

        # Add both pools
        for pool in [pool1, pool2]:
            pool_event = PoolCreatedEvent(
                pool_id=pool.pool_id,
                timestamp=base_time,
                pool=pool,
            )
            zone_watcher.on_pool_event(pool_event)

        # Enter first zone (98-102)
        candle1 = Candle(
            ts=base_time + timedelta(minutes=1),
            open=105.0,
            high=105.0,
            low=99.0,
            close=100.0,  # Touches zone 1
            volume=1500,
        )

        zone_events1 = zone_watcher.on_price_update(candle1)
        assert len(zone_events1) == 1
        assert zone_events1[0].zone_id == pool1.pool_id

        # Enter second zone (106-110)
        candle2 = Candle(
            ts=base_time + timedelta(minutes=2),
            open=100.0,
            high=108.0,
            low=100.0,
            close=108.0,  # Touches zone 2
            volume=1600,
        )

        zone_events2 = zone_watcher.on_price_update(candle2)
        assert len(zone_events2) == 1
        assert zone_events2[0].zone_id == pool2.pool_id

        # Verify both zones show entry
        stats = zone_watcher.get_stats()
        assert stats["zone_entries"] == 2
        assert stats["zones_tracked"] == 2
        assert stats["active_zones"] == 2

        # Verify different entry prices
        assert zone_events1[0].entry_price == 100.0
        assert zone_events2[0].entry_price == 108.0
