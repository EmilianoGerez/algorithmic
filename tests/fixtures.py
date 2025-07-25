from datetime import datetime, timedelta

from core.entities import Candle


def create_test_candles(count: int = 50, base_price: float = 100.0) -> list[Candle]:
    """Create synthetic candles for testing."""
    candles = []
    current_price = base_price
    base_time = datetime(2025, 1, 1, 9, 0)

    for i in range(count):
        # Simple random walk with slight upward bias
        price_change = (i % 3 - 1) * 0.5  # -0.5, 0, 0.5 pattern
        current_price += price_change

        # Create OHLCV with some spread
        open_price = current_price
        high_price = current_price + abs(price_change) + 0.2
        low_price = current_price - abs(price_change) - 0.1
        close_price = current_price + price_change * 0.5
        volume = 1000 + (i % 10) * 100  # Varying volume

        candle = Candle(
            ts=base_time + timedelta(minutes=i),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )
        candles.append(candle)
        current_price = close_price

    return candles


def create_trending_candles(count: int = 50, trend: str = "up") -> list[Candle]:
    """Create trending candles for regime testing."""
    candles = []
    current_price = 100.0
    base_time = datetime(2025, 1, 1, 9, 0)

    trend_direction = 1 if trend == "up" else -1

    for i in range(count):
        # Consistent trend with minor noise
        base_move = trend_direction * 0.3
        noise = (i % 5 - 2) * 0.1  # Small random component
        price_change = base_move + noise

        open_price = current_price
        close_price = current_price + price_change
        high_price = max(open_price, close_price) + 0.1
        low_price = min(open_price, close_price) - 0.1
        volume = 1000 + abs(price_change) * 500  # Volume increases with movement

        candle = Candle(
            ts=base_time + timedelta(minutes=i),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )
        candles.append(candle)
        current_price = close_price

    return candles
