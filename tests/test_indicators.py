from datetime import datetime

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.entities import Candle
from core.indicators import (
    ATR,
    EMA,
    INDICATOR_REGISTRY,
    IndicatorPack,
    Regime,
    VolumeSMA,
)
from tests.fixtures import create_test_candles, create_trending_candles


class TestEMA:
    def test_ema_initialization(self):
        ema = EMA(21)
        assert ema.period == 21
        assert ema.value is None

    def test_ema_first_value(self):
        ema = EMA(21)
        candle = Candle(
            ts=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
        )
        ema.update(candle)
        assert ema.value == 100.5  # First value should be close price

    def test_ema_calculation_manual(self):
        """Manual test of EMA calculation with known values."""
        ema = EMA(3)  # Short period for easy calculation
        # multiplier = 2 / (3 + 1)  # Should be 0.5

        # First candle
        candle1 = Candle(
            ts=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000,
        )
        ema.update(candle1)
        assert ema.value == 100.0

        # Second candle
        candle2 = Candle(
            ts=datetime.now(),
            open=100.0,
            high=103.0,
            low=99.0,
            close=102.0,
            volume=1000,
        )
        ema.update(candle2)
        # EMA = (102 - 100) * 0.5 + 100 = 101
        assert np.allclose(ema.value, 101.0, rtol=1e-6, atol=1e-8)

        # Third candle
        candle3 = Candle(
            ts=datetime.now(),
            open=102.0,
            high=104.0,
            low=101.0,
            close=98.0,
            volume=1000,
        )
        ema.update(candle3)
        # EMA = (98 - 101) * 0.5 + 101 = 99.5
        assert np.allclose(ema.value, 99.5, rtol=1e-6, atol=1e-8)


class TestATR:
    def test_atr_initialization(self):
        atr = ATR(14)
        assert atr.period == 14
        assert atr.value is None
        assert not atr.is_ready

    def test_atr_first_candle(self):
        atr = ATR(14)
        candle = Candle(
            ts=datetime.now(),
            open=100.0,
            high=102.0,
            low=98.0,
            close=101.0,
            volume=1000,
        )
        atr.update(candle)
        assert atr.value is None  # Need full period
        assert not atr.is_ready

    def test_atr_true_range_calculation(self):
        atr = ATR(2)  # Small period for testing

        # First candle
        candle1 = Candle(
            ts=datetime.now(),
            open=100.0,
            high=102.0,
            low=98.0,
            close=101.0,
            volume=1000,
        )
        atr.update(candle1)

        # Second candle with gap
        candle2 = Candle(
            ts=datetime.now(),
            open=105.0,
            high=106.0,
            low=104.0,
            close=105.5,
            volume=1000,
        )
        atr.update(candle2)

        # Should have ATR now
        assert atr.is_ready
        assert atr.value is not None

        # True range for candle2 should be max(106-104, 106-101, 104-101) = max(2, 5, 3) = 5
        # True range for candle1 was 102-98 = 4
        # ATR should be (4 + 5) / 2 = 4.5
        expected_atr = (4.0 + 5.0) / 2
        assert np.allclose(atr.value, expected_atr, rtol=1e-6, atol=1e-8)


class TestVolumeSMA:
    def test_volume_sma_initialization(self):
        vol_sma = VolumeSMA(20)
        assert vol_sma.period == 20
        assert vol_sma.value is None
        assert not vol_sma.is_ready

    def test_volume_sma_calculation(self):
        vol_sma = VolumeSMA(3)  # Small period for testing

        volumes = [1000, 1500, 2000]
        for _i, vol in enumerate(volumes):
            candle = Candle(
                ts=datetime.now(),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=vol,
            )
            vol_sma.update(candle)

        assert vol_sma.is_ready
        expected_sma = sum(volumes) / len(volumes)
        assert np.allclose(vol_sma.value, expected_sma, rtol=1e-6, atol=1e-8)

        # Test volume multiple
        expected_multiple = 3000 / expected_sma
        assert np.allclose(
            vol_sma.volume_multiple(3000), expected_multiple, rtol=1e-6, atol=1e-8
        )


class TestIndicatorPack:
    def test_indicator_pack_initialization(self):
        pack = IndicatorPack()
        assert pack.ema21_period == 21
        assert pack.ema50_period == 50
        assert pack.atr_period == 14
        assert pack.volume_sma_period == 20
        assert not pack.is_ready

    def test_indicator_pack_update_and_snapshot(self):
        pack = IndicatorPack(
            ema21_period=3, ema50_period=5, atr_period=3, volume_sma_period=3
        )

        candles = create_test_candles(10)

        # Update with candles
        for candle in candles:
            pack.update(candle)

        # Should be ready after enough candles
        assert pack.is_ready

        # Test snapshot
        snapshot = pack.snapshot()
        assert snapshot.timestamp == candles[-1].ts
        assert snapshot.ema21 is not None
        assert snapshot.ema50 is not None
        assert snapshot.atr is not None
        assert snapshot.volume_sma is not None
        assert snapshot.regime is not None
        assert snapshot.is_ready

    def test_regime_detection(self):
        """Test regime detection with trending data."""
        pack = IndicatorPack(
            ema21_period=5, ema50_period=10, atr_period=5, volume_sma_period=5
        )

        # Test bullish trend
        bull_candles = create_trending_candles(20, "up")
        for candle in bull_candles:
            pack.update(candle)

        snapshot = pack.snapshot()
        assert snapshot.regime == Regime.BULL
        assert snapshot.ema_aligned_bullish

        # Test bearish trend
        bear_pack = IndicatorPack(
            ema21_period=5, ema50_period=10, atr_period=5, volume_sma_period=5
        )
        bear_candles = create_trending_candles(20, "down")
        for candle in bear_candles:
            bear_pack.update(candle)

        bear_snapshot = bear_pack.snapshot()
        assert bear_snapshot.regime == Regime.BEAR
        assert bear_snapshot.ema_aligned_bearish


class TestRegimeErgonomics:
    """Test the ergonomic comparison methods for Regime enum."""

    def test_regime_bullish_properties(self):
        assert Regime.BULL.is_bullish
        assert not Regime.BULL.is_bearish
        assert not Regime.BULL.is_neutral
        assert Regime.BULL.is_trending

    def test_regime_bearish_properties(self):
        assert not Regime.BEAR.is_bullish
        assert Regime.BEAR.is_bearish
        assert not Regime.BEAR.is_neutral
        assert Regime.BEAR.is_trending

    def test_regime_neutral_properties(self):
        assert not Regime.NEUTRAL.is_bullish
        assert not Regime.NEUTRAL.is_bearish
        assert Regime.NEUTRAL.is_neutral
        assert not Regime.NEUTRAL.is_trending


class TestIndicatorRegistry:
    """Test the indicator registry for dynamic discovery."""

    def test_registry_basic_functionality(self):
        # Test indicator creation
        ema = INDICATOR_REGISTRY.create("ema", period=21)
        assert isinstance(ema, EMA)
        assert ema.period == 21

        atr = INDICATOR_REGISTRY.create("atr", period=14)
        assert isinstance(atr, ATR)
        assert atr.period == 14

    def test_registry_list_indicators(self):
        indicators = INDICATOR_REGISTRY.list_indicators()
        assert "ema" in indicators
        assert "atr" in indicators
        assert "volume_sma" in indicators

    def test_registry_unknown_indicator(self):
        with pytest.raises(KeyError, match="Indicator 'unknown' not found"):
            INDICATOR_REGISTRY.create("unknown", period=10)

    def test_registry_is_registered(self):
        assert INDICATOR_REGISTRY.is_registered("ema")
        assert INDICATOR_REGISTRY.is_registered("atr")
        assert not INDICATOR_REGISTRY.is_registered("unknown")


# Property-based tests with Hypothesis
@given(
    period=st.integers(min_value=2, max_value=10),
    num_candles=st.integers(min_value=15, max_value=50),
)
def test_ema_property_consistent_calculation(period, num_candles):
    """Property test: EMA calculation should be consistent and bounded."""
    candles = create_test_candles(num_candles)

    # Skip if not enough data
    if len(candles) < period + 5:
        return

    # Calculate EMA
    ema = EMA(period)
    values = []

    for candle in candles:
        ema.update(candle)
        if ema.value is not None:
            values.append(ema.value)

    # Basic properties
    assert len(values) > 0
    assert all(v > 0 for v in values)  # All prices should be positive

    # EMA should be relatively stable (no huge jumps)
    if len(values) > 1:
        max_change = max(abs(values[i] - values[i - 1]) for i in range(1, len(values)))
        assert max_change < 50  # Reasonable for our test data
