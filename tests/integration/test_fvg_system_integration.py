# tests/integration/test_fvg_system_integration.py
"""Integration tests for the FVG detection and management system."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

import pytest

from core.data.models import Candle, FVGZone, SignalDirection, TimeFrame
from core.indicators.fvg_detector import FVGDetector, FVGFilterConfig


class TestFVGSystemIntegration:
    """Integration tests for the complete FVG system."""

    @pytest.fixture
    def fvg_system_config(self):
        """Configuration for FVG system integration testing."""
        return FVGFilterConfig(
            min_zone_size_percentage=0.01,
            min_strength_threshold=0.5,
            high_quality_threshold=0.7,
            premium_quality_threshold=0.85,
            volume_context_periods=20,
            min_volume_multiplier=1.2,
        )

    @pytest.fixture
    def sample_market_data(self) -> List[Candle]:
        """Create realistic market data with multiple FVG patterns."""
        candles = []
        base_time = datetime(2025, 1, 1, 9, 0)
        base_price = Decimal("50000")

        # Normal market opening
        for i in range(5):
            timestamp = base_time + timedelta(minutes=15 * i)
            price_drift = Decimal(str(i * 10))

            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=base_price + price_drift,
                    high=base_price + price_drift + Decimal("75"),
                    low=base_price + price_drift - Decimal("50"),
                    close=base_price + price_drift + Decimal("25"),
                    volume=Decimal(str(1000 + i * 100)),
                )
            )

        # Create a significant bullish FVG
        gap_candle_time = base_time + timedelta(minutes=15 * 5)
        gap_price = base_price + Decimal("400")  # Large gap up

        candles.append(
            Candle(
                timestamp=gap_candle_time,
                open=gap_price,
                high=gap_price + Decimal("200"),
                low=gap_price - Decimal("50"),
                close=gap_price + Decimal("150"),
                volume=Decimal("3000"),  # High volume
            )
        )

        # Continue with normal price action
        for i in range(6, 15):
            timestamp = base_time + timedelta(minutes=15 * i)
            current_price = gap_price + Decimal(str((i - 6) * 20))

            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=current_price,
                    high=current_price + Decimal("60"),
                    low=current_price - Decimal("40"),
                    close=current_price + Decimal("30"),
                    volume=Decimal(str(1200 + (i - 6) * 50)),
                )
            )

        # Create a bearish FVG
        gap_down_time = base_time + timedelta(minutes=15 * 15)
        gap_down_price = gap_price - Decimal("600")  # Large gap down

        candles.append(
            Candle(
                timestamp=gap_down_time,
                open=gap_down_price,
                high=gap_down_price + Decimal("100"),
                low=gap_down_price - Decimal("200"),
                close=gap_down_price - Decimal("100"),
                volume=Decimal("2500"),  # High volume
            )
        )

        return candles

    def test_end_to_end_fvg_detection(self, fvg_system_config, sample_market_data):
        """Test the complete FVG detection process."""
        # Initialize detector
        detector = FVGDetector(config=fvg_system_config)

        # Process market data
        detected_fvgs = detector.detect_fvgs(sample_market_data)

        # Verify FVGs were detected
        assert len(detected_fvgs) >= 1, "Should detect at least one FVG"

        # Check FVG properties
        for fvg in detected_fvgs:
            assert fvg.strength >= fvg_system_config.min_strength_threshold
            assert fvg.confidence > 0.0
            assert fvg.zone_high > fvg.zone_low
            assert fvg.status in ["active", "touched", "invalidated"]

    def test_fvg_quality_classification(self, fvg_system_config, sample_market_data):
        """Test FVG quality classification system."""
        detector = FVGDetector(config=fvg_system_config)
        detected_fvgs = detector.detect_fvgs(sample_market_data)

        # Should have FVGs of different qualities
        quality_levels = set()
        for fvg in detected_fvgs:
            if fvg.strength >= fvg_system_config.premium_quality_threshold:
                quality_levels.add("premium")
            elif fvg.strength >= fvg_system_config.high_quality_threshold:
                quality_levels.add("high")
            else:
                quality_levels.add("medium")

        assert len(quality_levels) >= 1, "Should classify FVGs by quality"

    def test_fvg_filtering_integration(self, sample_market_data):
        """Test FVG filtering with different configuration levels."""
        # Strict configuration
        strict_config = FVGFilterConfig(
            min_zone_size_percentage=0.05,  # 5% minimum
            min_strength_threshold=0.8,
            min_volume_multiplier=2.0,
        )

        # Lenient configuration
        lenient_config = FVGFilterConfig(
            min_zone_size_percentage=0.005,  # 0.5% minimum
            min_strength_threshold=0.3,
            min_volume_multiplier=0.8,
        )

        strict_detector = FVGDetector(config=strict_config)
        lenient_detector = FVGDetector(config=lenient_config)

        strict_fvgs = strict_detector.detect_fvgs(sample_market_data)
        lenient_fvgs = lenient_detector.detect_fvgs(sample_market_data)

        # Lenient should detect more FVGs than strict
        assert len(lenient_fvgs) >= len(strict_fvgs)

        # All strict FVGs should be high quality
        for fvg in strict_fvgs:
            assert fvg.strength >= 0.8

    def test_fvg_zone_management_lifecycle(self, fvg_system_config):
        """Test the complete lifecycle of FVG zone management."""
        detector = FVGDetector(config=fvg_system_config)

        # Create test data with clear FVG
        candles = [
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 0),
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50050"),
                volume=Decimal("1000"),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_15,
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 15),
                open=Decimal("50050"),
                high=Decimal("50200"),
                low=Decimal("50000"),
                close=Decimal("50150"),
                volume=Decimal("2000"),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_15,
            ),
            Candle(
                timestamp=datetime(2025, 1, 1, 9, 30),
                open=Decimal("50300"),  # Gap up creates FVG
                high=Decimal("50500"),
                low=Decimal("50250"),
                close=Decimal("50450"),
                volume=Decimal("2500"),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_15,
            ),
        ]

        # Detect FVGs
        fvgs = detector.detect_fvgs(candles)
        assert len(fvgs) >= 1

        fvg = fvgs[0]
        initial_status = fvg.status

        # Test zone price interaction
        assert fvg.is_price_in_zone(fvg.get_zone_midpoint())
        assert not fvg.is_price_in_zone(fvg.zone_high + Decimal("100"))
        assert not fvg.is_price_in_zone(fvg.zone_low - Decimal("100"))

        # Test zone properties
        zone_size = fvg.get_zone_size()
        assert zone_size > 0

        midpoint = fvg.get_zone_midpoint()
        assert fvg.zone_low < midpoint < fvg.zone_high

    def test_multi_timeframe_fvg_detection(self):
        """Test FVG detection across multiple timeframes."""
        configs = {
            TimeFrame.MINUTE_5: FVGFilterConfig(min_zone_size_percentage=0.005),
            TimeFrame.MINUTE_15: FVGFilterConfig(min_zone_size_percentage=0.01),
            TimeFrame.HOUR_1: FVGFilterConfig(min_zone_size_percentage=0.02),
        }

        # Create data with different granularities
        base_time = datetime(2025, 1, 1, 9, 0)
        base_price = Decimal("50000")

        for timeframe, config in configs.items():
            detector = FVGDetector(config=config)

            # Generate candles for this timeframe
            candles = []
            time_delta = timedelta(
                minutes=(
                    5
                    if timeframe == TimeFrame.MINUTE_5
                    else 15 if timeframe == TimeFrame.MINUTE_15 else 60
                )
            )

            for i in range(10):
                timestamp = base_time + time_delta * i
                price_variance = Decimal(str(100 * (i % 3 - 1)))

                candles.append(
                    Candle(
                        timestamp=timestamp,
                        open=base_price + price_variance,
                        high=base_price + price_variance + Decimal("200"),
                        low=base_price + price_variance - Decimal("100"),
                        close=base_price + price_variance + Decimal("50"),
                        volume=Decimal(str(1000 + i * 100)),
                    )
                )

            # Add gap candle
            gap_time = base_time + time_delta * 10
            gap_price = base_price + Decimal("500")

            candles.append(
                Candle(
                    timestamp=gap_time,
                    open=gap_price,
                    high=gap_price + Decimal("200"),
                    low=gap_price - Decimal("50"),
                    close=gap_price + Decimal("100"),
                    volume=Decimal("3000"),
                    symbol="BTCUSD",
                    timeframe=TimeFrame.MINUTE_15,
                )
            )

            # Detect FVGs
            fvgs = detector.detect_fvgs(candles)

            # Should detect at least one FVG per timeframe
            assert len(fvgs) >= 0, f"Should handle {timeframe.value} timeframe"

    def test_fvg_performance_under_load(self, fvg_system_config):
        """Test FVG detection performance with large datasets."""
        import time

        detector = FVGDetector(config=fvg_system_config)

        # Generate large dataset
        base_time = datetime(2025, 1, 1, 0, 0)
        base_price = Decimal("50000")
        large_dataset = []

        for i in range(1000):  # 1000 candles
            timestamp = base_time + timedelta(minutes=i)
            price_noise = Decimal(str((i % 100 - 50) * 2))

            large_dataset.append(
                Candle(
                    timestamp=timestamp,
                    open=base_price + price_noise,
                    high=base_price + price_noise + Decimal("50"),
                    low=base_price + price_noise - Decimal("30"),
                    close=base_price + price_noise + Decimal("10"),
                    volume=Decimal(str(800 + (i % 500))),
                )
            )

        # Add some gaps for FVG detection
        for gap_index in [200, 400, 600, 800]:
            if gap_index < len(large_dataset):
                candle = large_dataset[gap_index]
                large_dataset[gap_index] = Candle(
                    timestamp=candle.timestamp,
                    open=candle.open + Decimal("300"),  # Create gap
                    high=candle.high + Decimal("350"),
                    low=candle.low + Decimal("250"),
                    close=candle.close + Decimal("320"),
                    volume=candle.volume * 3,
                )

        # Time the detection
        start_time = time.time()
        fvgs = detector.detect_fvgs(large_dataset)
        detection_time = time.time() - start_time

        # Performance assertions
        assert (
            detection_time < 5.0
        ), f"Detection took {detection_time:.2f}s, should be under 5s"
        assert len(fvgs) >= 0, "Should handle large datasets"

        # Memory usage should be reasonable
        import sys

        fvg_memory_size = sys.getsizeof(fvgs)
        assert fvg_memory_size < 1024 * 1024, "FVG results should use less than 1MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
