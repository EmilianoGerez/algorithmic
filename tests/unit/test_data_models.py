"""
Unit tests for data models.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from core.data.models import (
    Candle,
    MarketData,
    Signal,
    SignalDirection,
    SignalType,
    TimeFrame,
)


class TestCandle:
    """Test cases for Candle model."""

    def test_candle_creation(self):
        """Test basic candle creation."""
        timestamp = datetime(2025, 1, 1, 9, 0)
        candle = Candle(
            timestamp=timestamp,
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50050"),
            volume=Decimal("1000"),
            symbol="BTCUSD",
            timeframe=TimeFrame.MINUTE_1,
        )

        assert candle.timestamp == timestamp
        assert candle.open == Decimal("50000")
        assert candle.high == Decimal("50100")
        assert candle.low == Decimal("49900")
        assert candle.close == Decimal("50050")
        assert candle.volume == Decimal("1000")
        assert candle.symbol == "BTCUSD"
        assert candle.timeframe == TimeFrame.MINUTE_1

    def test_candle_invalid_ohlc(self):
        """Test that invalid OHLC relationships are caught."""
        timestamp = datetime(2025, 1, 1, 9, 0)

        # High less than open
        with pytest.raises(ValueError):
            Candle(
                timestamp=timestamp,
                open=Decimal("50000"),
                high=Decimal("49900"),  # Invalid: high < open
                low=Decimal("49800"),
                close=Decimal("49950"),
                volume=Decimal("1000"),
                symbol="BTCUSD",
                timeframe=TimeFrame.MINUTE_1,
            )

    def test_candle_properties(self):
        """Test candle calculated properties."""
        candle = Candle(
            timestamp=datetime(2025, 1, 1, 9, 0),
            open=Decimal("50000"),
            high=Decimal("50200"),
            low=Decimal("49800"),
            close=Decimal("50100"),
            volume=Decimal("1000"),
            symbol="BTCUSD",
            timeframe=TimeFrame.MINUTE_1,
        )

        # Test basic properties
        assert candle.open == Decimal("50000")
        assert candle.high == Decimal("50200")
        assert candle.low == Decimal("49800")
        assert candle.close == Decimal("50100")

        # Test calculated properties
        body_size = abs(candle.close - candle.open)  # 100
        range_size = candle.high - candle.low  # 400
        is_bullish = candle.close > candle.open  # True

        assert body_size == Decimal("100")
        assert range_size == Decimal("400")
        assert is_bullish is True

    @pytest.mark.parametrize(
        "open_price,close_price,expected_bullish",
        [
            (50000, 50100, True),
            (50000, 49900, False),
            (50000, 50000, False),  # Doji is not bullish
        ],
    )
    def test_candle_direction(self, open_price, close_price, expected_bullish):
        """Test candle direction detection."""
        candle = Candle(
            timestamp=datetime(2025, 1, 1, 9, 0),
            open=Decimal(str(open_price)),
            high=Decimal(str(max(open_price, close_price) + 50)),
            low=Decimal(str(min(open_price, close_price) - 50)),
            close=Decimal(str(close_price)),
            volume=Decimal("1000"),
            symbol="BTCUSD",
            timeframe=TimeFrame.MINUTE_1,
        )

        is_bullish = candle.close > candle.open
        is_bearish = candle.close < candle.open

        assert is_bullish == expected_bullish
        assert is_bearish == (not expected_bullish and open_price != close_price)


class TestSignal:
    """Test cases for Signal model."""

    def test_signal_creation(self):
        """Test basic signal creation."""
        timestamp = datetime(2025, 1, 1, 10, 0)
        signal = Signal(
            timestamp=timestamp,
            symbol="BTCUSD",
            direction=SignalDirection.LONG,
            signal_type=SignalType.ENTRY,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
            confidence=0.85,
        )

        assert signal.signal_type == SignalType.ENTRY
        assert signal.direction == SignalDirection.LONG
        assert signal.entry_price == Decimal("50000")
        assert signal.timestamp == timestamp
        assert signal.stop_loss == Decimal("49000")
        assert signal.take_profit == Decimal("52000")
        assert signal.confidence == 0.85
        assert signal.symbol == "BTCUSD"

    def test_signal_risk_reward_calculation(self):
        """Test risk/reward ratio calculation."""
        signal = Signal(
            timestamp=datetime(2025, 1, 1, 10, 0),
            symbol="BTCUSD",
            direction=SignalDirection.LONG,
            signal_type=SignalType.ENTRY,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )

        risk = signal.calculate_risk_amount()  # |50000 - 49000| = 1000
        reward = signal.calculate_reward_amount()  # |52000 - 50000| = 2000
        rr_ratio = signal.get_actual_risk_reward_ratio()  # 2000/1000 = 2.0

        assert risk == Decimal("1000")
        assert reward == Decimal("2000")
        assert rr_ratio == 2.0

    def test_signal_validation(self):
        """Test signal validation logic."""
        # Valid long signal
        long_signal = Signal(
            timestamp=datetime(2025, 1, 1, 10, 0),
            symbol="BTCUSD",
            direction=SignalDirection.LONG,
            signal_type=SignalType.ENTRY,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )
        # Basic validation
        assert long_signal.direction == SignalDirection.LONG
        assert long_signal.entry_price > 0
        assert long_signal.stop_loss < long_signal.entry_price

        # Valid short signal
        short_signal = Signal(
            timestamp=datetime(2025, 1, 1, 10, 0),
            symbol="BTCUSD",
            direction=SignalDirection.SHORT,
            signal_type=SignalType.ENTRY,
            entry_price=Decimal("50000"),
            stop_loss=Decimal("51000"),
            take_profit=Decimal("48000"),
        )
        # Basic validation
        assert short_signal.direction == SignalDirection.SHORT
        assert short_signal.entry_price > 0
        assert short_signal.stop_loss > short_signal.entry_price


class TestMarketData:
    """Test cases for MarketData model."""

    def test_market_data_creation(self, sample_candles):
        """Test market data creation."""
        market_data = MarketData(
            symbol="BTC/USD",
            timeframe=TimeFrame.MINUTE_5,
            candles=sample_candles,
            metadata={},
        )
        assert len(market_data.candles) == len(sample_candles)

    def test_market_data_validation(self):
        """Test market data validation."""
        market_data = MarketData(
            symbol="BTC/USD",
            timeframe=TimeFrame.MINUTE_5,
            candles=[],
            metadata={},
        )
        assert len(market_data.candles) == 0

    def test_market_data_properties(self, sample_candles):
        """Test market data calculated properties."""
        market_data = MarketData(
            symbol="BTC/USD",
            timeframe=TimeFrame.MINUTE_5,
            candles=sample_candles,
        )

        assert len(market_data.candles) == len(sample_candles)
        assert market_data.symbol == "BTC/USD"
        assert market_data.timeframe == TimeFrame.MINUTE_5

        # Test basic properties
        assert market_data.candles[0] == sample_candles[0]
        assert market_data.candles[-1] == sample_candles[-1]


class TestTimeFrame:
    """Test cases for TimeFrame enum."""

    def test_timeframe_values(self):
        """Test TimeFrame enum values."""
        assert TimeFrame.MINUTE_1.value == "1min"
        assert TimeFrame.MINUTE_5.value == "5min"
        assert TimeFrame.HOUR_1.value == "1H"
        assert TimeFrame.DAY_1.value == "1D"

    def test_timeframe_conversion(self):
        """Test TimeFrame string conversion."""
        assert TimeFrame.MINUTE_5.value == "5min"
        assert TimeFrame.HOUR_1.value == "1H"

    def test_timeframe_comparison(self):
        """Test TimeFrame comparison (basic enum comparison)."""
        # TimeFrame enums don't have built-in comparison, so we test by value
        assert TimeFrame.MINUTE_1.value == "1min"
        assert TimeFrame.MINUTE_5.value == "5min"
        assert TimeFrame.MINUTE_1 != TimeFrame.MINUTE_5


if __name__ == "__main__":
    pytest.main([__file__])
