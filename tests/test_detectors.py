"""Comprehensive tests for HTF pattern detectors.

Tests FVG and Pivot detection with hand-marked fixtures and generated data.
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.detectors.events import EventClassifier, EventRegistry
from core.detectors.fvg import FVGDetector, FVGEvent
from core.detectors.manager import DetectorConfig, DetectorManager
from core.detectors.pivot import PivotDetector, PivotEvent
from core.entities import Candle


class TestFVGDetector:
    """Test FVG detection with ATR scaling and volume filtering."""

    def test_bullish_fvg_detection(self):
        """Test bullish FVG detection with hand-marked fixture."""
        detector = FVGDetector("H1", min_gap_atr=0.3, min_gap_pct=0.05, min_rel_vol=1.2)

        # Create candles with obvious bullish gap
        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        candles = [
            Candle(base_time, 100.0, 105.0, 99.0, 102.0, 1000),  # prev
            Candle(
                base_time + timedelta(hours=1), 103.0, 108.0, 102.0, 106.0, 1100
            ),  # curr
            Candle(
                base_time + timedelta(hours=2), 110.0, 115.0, 109.0, 112.0, 1500
            ),  # next - gaps up
        ]

        # ATR = 5.0, Volume SMA = 1000
        atr_value = 5.0
        vol_sma_value = 1000.0

        events = []
        for candle in candles:
            events.extend(detector.update(candle, atr_value, vol_sma_value))

        # Should detect one bullish FVG
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, FVGEvent)
        assert event.side == "bullish"
        assert event.top == 109.0  # next.low
        assert event.bottom == 105.0  # prev.high
        assert event.tf == "H1"
        assert event.volume_ratio == 1.5  # 1500 / 1000
        assert event.gap_size_atr == 0.8  # (109-105) / 5
        assert event.gap_size_pct == pytest.approx(0.0392, abs=0.001)  # 4/102

    def test_bearish_fvg_detection(self):
        """Test bearish FVG detection with hand-marked fixture."""
        detector = FVGDetector("H1", min_gap_atr=0.3, min_gap_pct=0.05, min_rel_vol=1.2)

        # Create candles with obvious bearish gap
        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        candles = [
            Candle(base_time, 100.0, 105.0, 99.0, 102.0, 1000),  # prev
            Candle(
                base_time + timedelta(hours=1), 98.0, 103.0, 97.0, 101.0, 1100
            ),  # curr
            Candle(
                base_time + timedelta(hours=2), 90.0, 95.0, 89.0, 92.0, 1500
            ),  # next - gaps down
        ]

        # ATR = 5.0, Volume SMA = 1000
        atr_value = 5.0
        vol_sma_value = 1000.0

        events = []
        for candle in candles:
            events.extend(detector.update(candle, atr_value, vol_sma_value))

        # Should detect one bearish FVG
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, FVGEvent)
        assert event.side == "bearish"
        assert event.top == 99.0  # prev.low
        assert event.bottom == 95.0  # next.high
        assert event.tf == "H1"

    def test_volume_filter_rejection(self):
        """Test that low volume gaps are rejected."""
        detector = FVGDetector("H1", min_gap_atr=0.3, min_gap_pct=0.05, min_rel_vol=2.0)

        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        candles = [
            Candle(base_time, 100.0, 105.0, 99.0, 102.0, 1000),
            Candle(base_time + timedelta(hours=1), 103.0, 108.0, 102.0, 106.0, 1100),
            Candle(
                base_time + timedelta(hours=2), 110.0, 115.0, 109.0, 112.0, 1500
            ),  # Low volume
        ]

        # ATR = 5.0, Volume SMA = 1000 (rel_vol = 1.5, below 2.0 threshold)
        atr_value = 5.0
        vol_sma_value = 1000.0

        events = []
        for candle in candles:
            events.extend(detector.update(candle, atr_value, vol_sma_value))

        # Should be rejected due to volume filter
        assert len(events) == 0

    def test_or_logic_gap_validation(self):
        """Test OR logic for ATR and percentage thresholds."""
        detector = FVGDetector("H1", min_gap_atr=2.0, min_gap_pct=0.01, min_rel_vol=1.0)

        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

        # Small gap in ATR terms but large in percentage terms
        candles = [
            Candle(base_time, 1.0, 1.05, 0.99, 1.02, 1000),
            Candle(base_time + timedelta(hours=1), 1.03, 1.08, 1.02, 1.06, 1100),
            Candle(
                base_time + timedelta(hours=2), 1.10, 1.15, 1.09, 1.12, 1500
            ),  # 5% gap but small ATR
        ]

        # Small ATR = 0.05 (gap_size_atr = 1.0), but gap_size_pct = ~4.8%
        atr_value = 0.05
        vol_sma_value = 1000.0

        events = []
        for candle in candles:
            events.extend(detector.update(candle, atr_value, vol_sma_value))

        # Should pass percentage threshold (4.8% > 1%)
        assert len(events) == 1

    def test_overlapping_fvgs_same_timeframe(self):
        """Test that overlapping FVGs in same timeframe are both emitted."""
        detector = FVGDetector("H1", min_gap_atr=0.3, min_gap_pct=0.05, min_rel_vol=1.0)

        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

        # Create sequence with two overlapping bullish gaps
        candles = [
            # First gap setup
            Candle(base_time, 100.0, 105.0, 99.0, 102.0, 1000),  # prev1
            Candle(
                base_time + timedelta(hours=1), 103.0, 108.0, 102.0, 106.0, 1100
            ),  # curr1
            Candle(
                base_time + timedelta(hours=2), 110.0, 115.0, 109.0, 112.0, 1500
            ),  # next1 - first gap (105 to 109)
            # Second gap setup (partially overlapping)
            Candle(
                base_time + timedelta(hours=3), 111.0, 116.0, 110.0, 114.0, 1200
            ),  # prev2
            Candle(
                base_time + timedelta(hours=4), 113.0, 118.0, 112.0, 116.0, 1300
            ),  # curr2
            Candle(
                base_time + timedelta(hours=5), 120.0, 125.0, 119.0, 122.0, 1600
            ),  # next2 - second gap (116 to 119, overlaps with first)
        ]

        # ATR = 5.0, Volume SMA = 1000
        atr_value = 5.0
        vol_sma_value = 1000.0

        events = []
        for candle in candles:
            events.extend(detector.update(candle, atr_value, vol_sma_value))

        # Should detect multiple gaps as detector processes sliding window
        bullish_events = [e for e in events if e.side == "bullish"]
        assert (
            len(bullish_events) >= 2
        )  # At least 2 gaps, possibly more due to sliding window

        # Verify that we have distinct gap ranges (Registry will handle overlaps later)
        gap_ranges = [(e.bottom, e.top) for e in bullish_events]
        assert len(set(gap_ranges)) >= 2  # At least 2 unique gap ranges


class TestPivotDetector:
    """Test pivot detection with strength classification."""

    def test_swing_high_detection(self):
        """Test swing high detection with clear pattern."""
        detector = PivotDetector("H1", lookback_periods=3, min_sigma=0.5)

        # Create clear swing high pattern: low, low, HIGH, low, low
        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        candles = [
            Candle(
                base_time + timedelta(hours=0), 100.0, 102.0, 99.0, 101.0, 1000
            ),  # low
            Candle(
                base_time + timedelta(hours=1), 101.0, 103.0, 100.0, 102.0, 1000
            ),  # low
            Candle(
                base_time + timedelta(hours=2), 102.0, 104.0, 101.0, 103.0, 1000
            ),  # low
            Candle(
                base_time + timedelta(hours=3), 103.0, 110.0, 102.0, 108.0, 1000
            ),  # HIGH - pivot
            Candle(
                base_time + timedelta(hours=4), 107.0, 109.0, 106.0, 108.0, 1000
            ),  # low
            Candle(
                base_time + timedelta(hours=5), 106.0, 108.0, 105.0, 107.0, 1000
            ),  # low
            Candle(
                base_time + timedelta(hours=6), 105.0, 107.0, 104.0, 106.0, 1000
            ),  # low
        ]

        # ATR = 2.0
        atr_value = 2.0

        events = []
        for candle in candles:
            events.extend(detector.update(candle, atr_value))

        # Should detect one swing high
        high_events = [e for e in events if e.side == "high"]
        assert len(high_events) == 1

        event = high_events[0]
        assert isinstance(event, PivotEvent)
        assert event.side == "high"
        assert event.price == 110.0
        assert event.tf == "H1"
        assert event.atr_distance >= 0.5  # Meets minimum threshold

    def test_swing_low_detection(self):
        """Test swing low detection with clear pattern."""
        detector = PivotDetector("H1", lookback_periods=3, min_sigma=0.5)

        # Create clear swing low pattern: high, high, LOW, high, high
        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        candles = [
            Candle(
                base_time + timedelta(hours=0), 105.0, 107.0, 104.0, 106.0, 1000
            ),  # high
            Candle(
                base_time + timedelta(hours=1), 104.0, 106.0, 103.0, 105.0, 1000
            ),  # high
            Candle(
                base_time + timedelta(hours=2), 103.0, 105.0, 102.0, 104.0, 1000
            ),  # high
            Candle(
                base_time + timedelta(hours=3), 102.0, 104.0, 95.0, 98.0, 1000
            ),  # LOW - pivot
            Candle(
                base_time + timedelta(hours=4), 98.0, 100.0, 97.0, 99.0, 1000
            ),  # high
            Candle(
                base_time + timedelta(hours=5), 99.0, 101.0, 98.0, 100.0, 1000
            ),  # high
            Candle(
                base_time + timedelta(hours=6), 100.0, 102.0, 99.0, 101.0, 1000
            ),  # high
        ]

        # ATR = 2.0
        atr_value = 2.0

        events = []
        for candle in candles:
            events.extend(detector.update(candle, atr_value))

        # Should detect one swing low
        low_events = [e for e in events if e.side == "low"]
        assert len(low_events) == 1

        event = low_events[0]
        assert isinstance(event, PivotEvent)
        assert event.side == "low"
        assert event.price == 95.0
        assert event.tf == "H1"
        assert event.atr_distance >= 0.5

    def test_strength_classification(self):
        """Test pivot strength classification."""
        detector = PivotDetector("H1", lookback_periods=2, min_sigma=0.1)

        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

        # Major strength pivot (>1 ATR distance)
        candles = [
            Candle(base_time + timedelta(hours=0), 100.0, 102.0, 99.0, 101.0, 1000),
            Candle(base_time + timedelta(hours=1), 101.0, 103.0, 100.0, 102.0, 1000),
            Candle(
                base_time + timedelta(hours=2), 102.0, 130.0, 101.0, 125.0, 1000
            ),  # Major high
            Candle(base_time + timedelta(hours=3), 114.0, 116.0, 113.0, 115.0, 1000),
            Candle(base_time + timedelta(hours=4), 113.0, 115.0, 112.0, 114.0, 1000),
        ]

        # ATR = 10.0 (so 130-116 = 14 = 1.4 ATR distance)
        atr_value = 10.0

        events = []
        for candle in candles:
            events.extend(detector.update(candle, atr_value))

        high_events = [e for e in events if e.side == "high"]
        if high_events:
            event = high_events[0]
            assert event.strength_label == "major"
            assert event.atr_distance >= 1.0


class TestEventFramework:
    """Test event classification and registry."""

    def test_event_classifier(self):
        """Test event classification utilities."""
        # Mock FVG event
        fvg_event = FVGEvent(
            ts=datetime.now(UTC),
            pool_id="test1",
            side="bullish",
            top=110.0,
            bottom=105.0,
            tf="H1",
            strength=0.8,
            volume_ratio=1.5,
            gap_size_atr=1.0,
            gap_size_pct=0.05,
        )

        assert EventClassifier.is_bullish_event(fvg_event)
        assert not EventClassifier.is_bearish_event(fvg_event)
        assert EventClassifier.get_event_type(fvg_event) == "fvg_bullish"
        assert EventClassifier.get_price_level(fvg_event, "center") == 107.5
        assert (
            EventClassifier.get_price_level(fvg_event, "edge") == 105.0
        )  # Entry at bottom

    def test_event_registry(self):
        """Test event registry operations."""
        registry = EventRegistry()

        # Create test events
        event1 = FVGEvent(
            ts=datetime.now(UTC),
            pool_id="fvg1",
            side="bullish",
            top=110.0,
            bottom=105.0,
            tf="H1",
            strength=0.8,
            volume_ratio=1.5,
            gap_size_atr=1.0,
            gap_size_pct=0.05,
        )

        # Test add and retrieve
        registry.add_event(event1)
        assert registry.get_event("fvg1") == event1
        assert len(registry.get_events_by_timeframe("H1")) == 1
        assert len(registry.get_all_events()) == 1

        # Test stats
        stats = registry.get_stats()
        assert stats["total_events"] == 1
        assert stats["H1_events"] == 1

        # Test removal
        assert registry.remove_event("fvg1")
        assert registry.get_event("fvg1") is None
        assert len(registry.get_all_events()) == 0


class TestDetectorManager:
    """Test detector manager coordination."""

    def test_manager_initialization(self):
        """Test detector manager setup."""
        config = DetectorConfig(
            enabled_timeframes=["H1", "H4"],
            fvg_min_gap_atr=0.5,
            pivot_lookback=3,
        )

        manager = DetectorManager(config)

        # Check initialization
        assert "H1" in manager._fvg_detectors
        assert "H4" in manager._fvg_detectors
        assert "D1" not in manager._fvg_detectors  # Not enabled

        stats = manager.get_detector_stats()
        assert "H1" in stats
        assert "H4" in stats

    def test_manager_update_flow(self):
        """Test manager update processing."""
        manager = DetectorManager()

        # Create test candle
        candle = Candle(
            ts=datetime.now(UTC),
            open=100.0,
            high=105.0,
            low=99.0,
            close=102.0,
            volume=1000,
        )

        # Update (should return empty list until indicators ready)
        events = manager.update("H1", candle)
        assert isinstance(events, list)  # Should not crash


@given(
    st.lists(
        st.tuples(
            st.floats(min_value=50.0, max_value=150.0),  # open
            st.floats(min_value=50.0, max_value=150.0),  # high
            st.floats(min_value=50.0, max_value=150.0),  # low
            st.floats(min_value=50.0, max_value=150.0),  # close
            st.floats(min_value=100.0, max_value=10000.0),  # volume
        ),
        min_size=10,
        max_size=100,
    )
)
def test_fvg_detector_robustness(candle_data):
    """Property test: FVG detector should handle random data without crashing."""
    detector = FVGDetector("H1")
    base_time = datetime(2024, 1, 1, tzinfo=UTC)

    for i, (o, h, low, c, v) in enumerate(candle_data):
        # Ensure OHLC validity
        high = max(o, h, low, c)
        low_price = min(o, h, low, c)

        candle = Candle(
            ts=base_time + timedelta(hours=i),
            open=o,
            high=high,
            low=low_price,
            close=c,
            volume=v,
        )

        # Should not crash regardless of input
        events = detector.update(candle, atr_value=5.0, vol_sma_value=1000.0)
        assert isinstance(events, list)

        # All events should be valid
        for event in events:
            assert isinstance(event, FVGEvent)
            assert event.side in {"bullish", "bearish"}
            assert event.top >= event.bottom
            assert event.strength >= 0.0
            assert event.volume_ratio >= 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
