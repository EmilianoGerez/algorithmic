#!/usr/bin/env python3
"""
Test data quality improvements and configuration validation.

Validates the improvements suggested in the data quality analysis:
1. Volume filter explicit 0 check
2. ATR floor implementation
3. Configuration validation warnings
4. Linger window configuration test
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from core.entities import Candle
from core.indicators.atr import ATR
from core.indicators.snapshot import IndicatorSnapshot
from core.strategy.signal_candidate import CandidateConfig, FSMGuards, SignalCandidate
from core.strategy.signal_models import CandidateState, SignalDirection, ZoneType
from services.cli.cli import _validate_config


class TestVolumeFilterImprovements:
    """Test volume filter improvements."""

    def test_volume_filter_explicit_zero_disabled(self):
        """Test that volume_multiple=0 explicitly disables filter."""
        bar = Candle(
            ts=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=0.0,  # Zero volume
        )

        snapshot = IndicatorSnapshot(
            timestamp=datetime.now(),
            ema21=100.0,
            ema50=99.0,
            atr=2.0,
            volume_sma=1000.0,  # High volume SMA
            regime="bull",
            regime_with_slope=None,
            current_volume=0.0,
            current_close=102.0,
        )

        # Test explicit 0 disables filter
        assert FSMGuards.volume_ok(bar, snapshot, 0) is True

        # Test that positive multiple would fail with zero volume
        assert FSMGuards.volume_ok(bar, snapshot, 1.5) is False

    def test_volume_filter_negative_disabled(self):
        """Test that negative volume_multiple also disables filter."""
        bar = Candle(
            ts=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=0.0,
        )

        snapshot = IndicatorSnapshot(
            timestamp=datetime.now(),
            ema21=100.0,
            ema50=99.0,
            atr=2.0,
            volume_sma=1000.0,
            regime="bull",
            regime_with_slope=None,
            current_volume=0.0,
            current_close=102.0,
        )

        # Test negative values disable filter
        assert FSMGuards.volume_ok(bar, snapshot, -1.0) is True
        assert FSMGuards.volume_ok(bar, snapshot, -0.5) is True


class TestATRFloorImprovements:
    """Test ATR floor implementation."""

    def test_atr_floor_prevents_micro_atr(self):
        """Test that ATR floor prevents micro-ATR from identical bars."""
        atr = ATR(period=3)

        # Create identical OHLC bars (micro ATR scenario)
        identical_bar = Candle(
            ts=datetime.now(),
            open=100.0,
            high=100.0,  # Same as open
            low=100.0,  # Same as open
            close=100.0,  # Same as open
            volume=1000.0,
        )

        # Feed 3 identical bars
        for _ in range(3):
            atr.update(identical_bar)

        # ATR should be floored at minimum tick size
        assert atr.is_ready
        assert atr.value >= 0.00001  # ATR floor
        assert atr.value == 0.00001  # Should be exactly the floor

    def test_atr_floor_doesnt_affect_normal_atr(self):
        """Test that ATR floor doesn't affect normal ATR values."""
        atr = ATR(period=3)

        # Create bars with normal volatility
        bars = [
            Candle(datetime.now(), 100.0, 105.0, 95.0, 102.0, 1000.0),
            Candle(datetime.now(), 102.0, 107.0, 98.0, 104.0, 1000.0),
            Candle(datetime.now(), 104.0, 109.0, 99.0, 106.0, 1000.0),
        ]

        for bar in bars:
            atr.update(bar)

        # ATR should be much higher than floor
        assert atr.is_ready
        assert atr.value > 0.1  # Much higher than floor


class TestConfigurationValidation:
    """Test configuration validation warnings."""

    def test_volume_filter_disabled_warning(self, caplog):
        """Test that disabled volume filter emits warning."""
        config = {
            "candidate": {"filters": {"volume_multiple": 0}},
            "data": {"timeframe": "5m"},
            "aggregation": {"source_tf_minutes": 5},
            "execution": {},
        }

        with caplog.at_level(logging.WARNING):
            _validate_config(config, logging.getLogger())

        assert "Volume filter disabled" in caplog.text

    def test_timeframe_mismatch_warning(self, caplog):
        """Test that timeframe mismatch emits warning."""
        config = {
            "candidate": {"filters": {"volume_multiple": 1.2}},
            "data": {"timeframe": "1m"},  # 1 minute
            "aggregation": {"source_tf_minutes": 5},  # 5 minutes - mismatch!
            "execution": {},
        }

        with caplog.at_level(logging.WARNING):
            _validate_config(config, logging.getLogger())

        assert "doesn't match aggregation source_tf_minutes" in caplog.text

    def test_event_dumping_info(self, caplog):
        """Test that event dumping emits info message."""
        config = {
            "candidate": {"filters": {"volume_multiple": 1.2}},
            "data": {"timeframe": "5m"},
            "aggregation": {"source_tf_minutes": 5},
            "execution": {"dump_events": True},
        }

        with caplog.at_level(logging.INFO):
            _validate_config(config, logging.getLogger())

        assert "Event dumping enabled" in caplog.text


class TestLingerWindowConfiguration:
    """Test linger window configuration as suggested."""

    def test_linger_window_configuration(self):
        """Test that linger window is correctly configured."""
        config = CandidateConfig(linger_minutes=90)

        # Verify linger delta matches configuration
        linger_delta = timedelta(minutes=config.linger_minutes)
        assert linger_delta == timedelta(minutes=90)

        # Test that linger window configuration is accessible
        assert config.linger_minutes == 90

    def test_current_base_yaml_linger_setting(self):
        """Test that base.yaml has the correct linger setting."""
        config_path = Path("configs/base.yaml")

        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)

            linger_minutes = (
                config.get("candidate", {}).get("filters", {}).get("linger_minutes", 60)
            )
            assert linger_minutes == 90, (
                f"Expected linger_minutes=90, got {linger_minutes}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
