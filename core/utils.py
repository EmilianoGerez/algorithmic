"""
Core utility functions for the algorithmic trading platform.

This module provides common utility functions used throughout the system,
including price formatting, symbol utilities, and other helper functions.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_EVEN, Decimal


def format_price(price: float, tick_size: float) -> float:
    """Format price to match asset-specific tick size precision.

    Args:
        price: Raw price value
        tick_size: Asset-specific tick size (e.g., 0.1 for BTCUSD, 0.00001 for EURUSD)

    Returns:
        Price rounded to the nearest tick size

    Examples:
        >>> format_price(100.157, 0.1)
        100.2
        >>> format_price(1.23456, 0.00001)
        1.23456
        >>> format_price(1.234567, 0.00001)
        1.23457
    """
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")

    # Use Decimal for precise arithmetic
    price_dec = Decimal(str(price))
    tick_dec = Decimal(str(tick_size))

    # Round to nearest tick using banker's rounding
    ticks = (price_dec / tick_dec).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    rounded = ticks * tick_dec

    return float(rounded)


def get_price_precision(tick_size: float) -> int:
    """Get decimal precision for formatting prices.

    Args:
        tick_size: Asset-specific tick size

    Returns:
        Number of decimal places needed to display the tick size

    Examples:
        >>> get_price_precision(0.1)
        1
        >>> get_price_precision(0.00001)
        5
        >>> get_price_precision(1.0)
        0
    """
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")

    # Count decimal places by converting to string
    decimal_places = 0
    temp_tick = tick_size

    while temp_tick < 1:
        temp_tick *= 10
        decimal_places += 1

    return decimal_places


def format_price_display(price: float, tick_size: float) -> str:
    """Format price for display with appropriate decimal places.

    Args:
        price: Price value to format
        tick_size: Asset-specific tick size

    Returns:
        Formatted price string with appropriate decimal places

    Examples:
        >>> format_price_display(100.1, 0.1)
        '100.1'
        >>> format_price_display(1.23456, 0.00001)
        '1.23456'
    """
    formatted_price = format_price(price, tick_size)
    precision = get_price_precision(tick_size)
    return f"{formatted_price:.{precision}f}"
