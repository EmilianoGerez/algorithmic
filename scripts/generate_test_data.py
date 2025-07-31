"""
Generate synthetic market data for testing Phase 8 integration.
"""

import csv
import math
import random
from datetime import datetime, timedelta
from typing import Any


def generate_ohlcv_data(
    symbol: str = "BTCUSDT", days: int = 30, start_price: float = 50000.0
) -> list[dict[str, Any]]:
    """Generate synthetic OHLCV data for testing.

    Args:
        symbol: Trading symbol
        days: Number of days of data
        start_price: Starting price

    Returns:
        List of OHLCV dictionaries
    """
    data = []
    current_price = start_price
    current_time = datetime(2024, 1, 1, 0, 0, 0)

    for day in range(days):
        for _minute in range(1440):  # 1440 minutes per day
            # Generate some price movement with trend and noise
            trend = 0.0001 * math.sin(day * 0.1)  # Slow trend
            noise = random.gauss(0, 0.002)  # Random noise
            price_change = (trend + noise) * current_price

            # Calculate OHLC for this minute
            open_price = current_price

            # Random intrabar movement
            high_offset = random.uniform(0, 0.01) * current_price
            low_offset = random.uniform(0, 0.01) * current_price

            high_price = open_price + high_offset
            low_price = open_price - low_offset
            close_price = max(low_price, min(high_price, open_price + price_change))

            # Ensure OHLC relationships are valid
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)

            # Random volume
            volume = random.uniform(10, 1000)

            data.append(
                {
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(low_price, 2),
                    "close": round(close_price, 2),
                    "volume": round(volume, 4),
                }
            )

            current_price = close_price
            current_time += timedelta(minutes=1)

    return data


def create_test_data_file(filename: str = "test_data.csv", days: int = 30) -> None:
    """Create test data CSV file.

    Args:
        filename: Output filename
        days: Number of days of data
    """
    data = generate_ohlcv_data(days=days)

    with open(filename, "w", newline="") as f:
        fieldnames = ["timestamp", "open", "high", "low", "close", "volume"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"Created {filename} with {len(data)} rows ({days} days of 1-minute data)")


if __name__ == "__main__":
    create_test_data_file("test_data.csv", days=30)
