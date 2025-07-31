"""Tests for core utility functions."""

import pytest

from core.utils import format_price, format_price_display, get_price_precision


class TestPriceFormatting:
    """Test price formatting utilities."""

    def test_format_price_btc(self):
        """Test BTC price formatting with 0.1 tick size."""
        assert format_price(100.157, 0.1) == 100.2  # 100.157 rounds up to 100.2
        assert format_price(100.14, 0.1) == 100.1  # 100.14 rounds down to 100.1
        assert format_price(100.16, 0.1) == 100.2  # 100.16 rounds up to 100.2
        assert format_price(99.95, 0.1) == 100.0  # 99.95 rounds up to 100.0

    def test_format_price_forex(self):
        """Test forex price formatting with 0.00001 tick size."""
        assert format_price(1.23456, 0.00001) == 1.23456
        assert format_price(1.234567, 0.00001) == 1.23457
        assert format_price(1.234564, 0.00001) == 1.23456

    def test_format_price_invalid_tick_size(self):
        """Test error handling for invalid tick sizes."""
        with pytest.raises(ValueError, match="tick_size must be positive"):
            format_price(100.0, 0.0)

        with pytest.raises(ValueError, match="tick_size must be positive"):
            format_price(100.0, -0.1)

    def test_get_price_precision(self):
        """Test decimal precision calculation."""
        assert get_price_precision(0.1) == 1
        assert get_price_precision(0.01) == 2
        assert get_price_precision(0.00001) == 5
        assert get_price_precision(1.0) == 0

    def test_get_price_precision_invalid(self):
        """Test error handling for invalid tick sizes."""
        with pytest.raises(ValueError, match="tick_size must be positive"):
            get_price_precision(0.0)

        with pytest.raises(ValueError, match="tick_size must be positive"):
            get_price_precision(-0.1)

    def test_format_price_display(self):
        """Test price display formatting."""
        assert format_price_display(100.157, 0.1) == "100.2"  # Updated expectation
        assert format_price_display(1.23456, 0.00001) == "1.23456"
        assert format_price_display(1.234567, 0.00001) == "1.23457"
        assert format_price_display(50000.0, 1.0) == "50000"

    def test_rounding_edge_cases(self):
        """Test edge cases for rounding."""
        # Test exact halfway cases (banker's rounding)
        assert format_price(100.05, 0.1) == 100.0  # Round to even
        assert format_price(100.15, 0.1) == 100.2  # Round to even

        # Test very small tick sizes
        assert format_price(1.000001, 0.000001) == 1.000001
        assert format_price(1.0000005, 0.000001) == 1.000000  # Round to even
