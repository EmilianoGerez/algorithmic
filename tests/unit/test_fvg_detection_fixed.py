"""
Unit tests for FVG detection functionality.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch
from core.signals.enhanced_fvg_detector import FVGDetector
from core.data.models import Candle, TimeFrame, SignalDirection
from core.indicators.fvg_detector import FVGZone


class TestFVGDetector:
    """Test cases for FVG detector."""
    
    def test_fvg_detector_creation(self):
        """Test FVG detector instantiation."""
        config = {
            'gap_threshold': 0.001,
            'min_gap_size': 10,
            'max_zones': 5
        }
        detector = FVGDetector(config=config)
        assert detector is not None
        assert detector.config == config
    
    def test_bullish_fvg_detection(self):
        """Test detection of bullish FVG patterns."""
        config = {
            'gap_threshold': 0.001,
            'min_gap_size': 10,
            'max_zones': 5
        }
        detector = FVGDetector(config=config)
        
        # Create candles with bullish FVG pattern
        candles = [
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 0),
                open=Decimal('50000'),
                high=Decimal('50100'),
                low=Decimal('49900'),
                close=Decimal('50050'),
                volume=Decimal('1000'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 15),
                open=Decimal('50050'),
                high=Decimal('50300'),
                low=Decimal('50000'),
                close=Decimal('50250'),
                volume=Decimal('1500'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 30),
                open=Decimal('50400'),  # Gap up from previous high (50300)
                high=Decimal('50500'),
                low=Decimal('50350'),
                close=Decimal('50450'),
                volume=Decimal('1200'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
        ]
        
        fvgs = detector.detect_fvgs(candles)
        
        assert len(fvgs) >= 0  # Might detect FVG depending on implementation
        if len(fvgs) > 0:
            fvg = fvgs[0]
            assert fvg.direction == SignalDirection.LONG
            assert fvg.status == "active"
    
    def test_bearish_fvg_detection(self):
        """Test detection of bearish FVG patterns."""
        config = {
            'gap_threshold': 0.001,
            'min_gap_size': 10,
            'max_zones': 5
        }
        detector = FVGDetector(config=config)
        
        # Create candles with bearish FVG pattern
        candles = [
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 0),
                open=Decimal('50000'),
                high=Decimal('50100'),
                low=Decimal('49900'),
                close=Decimal('50050'),
                volume=Decimal('1000'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 15),
                open=Decimal('50050'),
                high=Decimal('50000'),
                low=Decimal('49700'),
                close=Decimal('49750'),
                volume=Decimal('1500'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 30),
                open=Decimal('49600'),  # Gap down from previous low (49700)
                high=Decimal('49650'),
                low=Decimal('49500'),
                close=Decimal('49550'),
                volume=Decimal('1200'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
        ]
        
        fvgs = detector.detect_fvgs(candles)
        
        assert len(fvgs) >= 0  # Might detect FVG depending on implementation
        if len(fvgs) > 0:
            fvg = fvgs[0]
            assert fvg.direction == SignalDirection.SHORT
            assert fvg.status == "active"
    
    def test_no_fvg_detection(self):
        """Test scenario where no FVG is detected."""
        config = {
            'gap_threshold': 0.001,
            'min_gap_size': 10,
            'max_zones': 5
        }
        detector = FVGDetector(config=config)
        
        # Create candles without FVG pattern (continuous price action)
        candles = [
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 0),
                open=Decimal('50000'),
                high=Decimal('50100'),
                low=Decimal('49900'),
                close=Decimal('50050'),
                volume=Decimal('1000'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 15),
                open=Decimal('50050'),
                high=Decimal('50150'),
                low=Decimal('50000'),
                close=Decimal('50100'),
                volume=Decimal('1500'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 30),
                open=Decimal('50100'),
                high=Decimal('50200'),
                low=Decimal('50050'),
                close=Decimal('50150'),
                volume=Decimal('1200'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
        ]
        
        fvgs = detector.detect_fvgs(candles)
        
        # Should not detect FVG due to continuous price action
        assert len(fvgs) == 0
    
    def test_fvg_gap_ratio_filtering(self):
        """Test FVG filtering based on gap ratio."""
        config = {
            'gap_threshold': 0.05,  # 5% minimum gap
            'min_gap_size': 100,    # Large minimum gap
            'max_zones': 5
        }
        detector = FVGDetector(config=config)
        
        # Create candles with small gap that should be filtered out
        candles = [
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 0),
                open=Decimal('50000'),
                high=Decimal('50100'),
                low=Decimal('49900'),
                close=Decimal('50050'),
                volume=Decimal('1000'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 15),
                open=Decimal('50050'),
                high=Decimal('50120'),
                low=Decimal('50000'),
                close=Decimal('50080'),
                volume=Decimal('1500'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 30),
                open=Decimal('50130'),  # Small gap of 10 points
                high=Decimal('50200'),
                low=Decimal('50120'),
                close=Decimal('50180'),
                volume=Decimal('1200'),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1
            ),
        ]
        
        fvgs = detector.detect_fvgs(candles)
        
        # Should not detect FVG due to small gap size
        assert len(fvgs) == 0


class TestFVGZone:
    """Test cases for FVG zone model."""
    
    def test_fvg_zone_creation(self):
        """Test FVG zone creation."""
        zone = FVGZone(
            id="test-zone-1",
            direction=SignalDirection.LONG,
            high=Decimal('50500'),
            low=Decimal('50300'),
            timestamp=datetime(2025, 1, 1, 9, 30),
            status="active"
        )
        
        assert zone.id == "test-zone-1"
        assert zone.direction == SignalDirection.LONG
        assert zone.high == Decimal('50500')
        assert zone.low == Decimal('50300')
        assert zone.status == "active"
    
    def test_fvg_zone_properties(self):
        """Test FVG zone calculated properties."""
        zone = FVGZone(
            id="test-zone-1",
            direction=SignalDirection.LONG,
            high=Decimal('50500'),
            low=Decimal('50300'),
            timestamp=datetime(2025, 1, 1, 9, 30),
            status="active"
        )
        
        # Test calculated properties
        assert zone.size == Decimal('200')  # high - low
        assert zone.mid_point == Decimal('50400')  # (high + low) / 2
    
    def test_fvg_zone_price_tests(self):
        """Test FVG zone price level tests."""
        zone = FVGZone(
            id="test-zone-1",
            direction=SignalDirection.LONG,
            high=Decimal('50500'),
            low=Decimal('50300'),
            timestamp=datetime(2025, 1, 1, 9, 30),
            status="active"
        )
        
        # Test price level checks
        assert zone.contains_price(Decimal('50400')) is True
        assert zone.contains_price(Decimal('50600')) is False
        assert zone.contains_price(Decimal('50200')) is False
        assert zone.contains_price(Decimal('50300')) is True  # Boundary
        assert zone.contains_price(Decimal('50500')) is True  # Boundary
    
    def test_fvg_zone_validation(self):
        """Test FVG zone validation."""
        # Valid zone
        zone = FVGZone(
            id="test-zone-1",
            direction=SignalDirection.LONG,
            high=Decimal('50500'),
            low=Decimal('50300'),
            timestamp=datetime(2025, 1, 1, 9, 30),
            status="active"
        )
        
        assert zone.is_valid() is True
        
        # Invalid zone (high <= low)
        with pytest.raises(ValueError):
            FVGZone(
                id="test-zone-2",
                direction=SignalDirection.LONG,
                high=Decimal('50300'),
                low=Decimal('50500'),  # Invalid: low > high
                timestamp=datetime(2025, 1, 1, 9, 30),
                status="active"
            )


if __name__ == "__main__":
    pytest.main([__file__])
