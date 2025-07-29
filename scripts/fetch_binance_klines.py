#!/usr/bin/env python3
"""
Binance Historical Data Fetcher

Fetches OHLCV data from Binance (Spot or Futures) and saves it in the format
expected by our backtesting engine. Designed to replace poor-quality data
sources with high-quality exchange data.

Usage:
    python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-05-15T00:00:00 2025-05-20T00:00:00 --futures
    python scripts/fetch_binance_klines.py ETHUSDT 1h 2025-01-01T00:00:00 2025-01-31T23:59:59
"""

import argparse
import csv
import datetime as dt
import logging
import os
import time
from pathlib import Path
from typing import Optional

from tqdm import tqdm

# Timeframe mapping: name -> milliseconds
TF_MAP = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_629_746_000,  # Approximate month
}

logger = logging.getLogger(__name__)


def iso_timestamp(timestamp_ms: int) -> str:
    """Convert millisecond timestamp to ISO format expected by our engine."""
    return dt.datetime.fromtimestamp(timestamp_ms / 1000, dt.UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def fetch_binance_data(
    symbol: str,
    timeframe: str,
    start_time: str,
    end_time: str,
    output_file: Path,
    use_futures: bool = False,
    testnet: bool = False,
) -> None:
    """
    Fetch historical kline data from Binance and save to CSV.

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        timeframe: Kline interval (e.g., '5m', '1h', '1d')
        start_time: ISO format start time (e.g., '2025-05-15T00:00:00')
        end_time: ISO format end time (e.g., '2025-05-20T00:00:00')
        output_file: Path to save the CSV file
        use_futures: Whether to use Futures API instead of Spot
        testnet: Whether to use testnet (requires API keys)
    """
    try:
        from binance import Client
    except ImportError as err:
        raise ImportError(
            "python-binance library not installed. Run: pip install python-binance"
        ) from err

    # Get API credentials (optional for public data)
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if testnet and (not api_key or not api_secret):
        raise ValueError(
            "API keys required for testnet access. Set BINANCE_API_KEY and BINANCE_API_SECRET"
        )

    # Initialize client
    client = Client(api_key, api_secret, testnet=testnet)

    # Choose the appropriate klines function
    if use_futures:
        klines_func = client.futures_klines
        logger.info(f"Using Binance Futures API for {symbol}")
    else:
        klines_func = client.get_historical_klines
        logger.info(f"Using Binance Spot API for {symbol}")

    # Convert timeframe and timestamps
    interval_ms = TF_MAP[timeframe]
    start_ms = int(dt.datetime.fromisoformat(start_time).timestamp() * 1000)
    end_ms = int(dt.datetime.fromisoformat(end_time).timestamp() * 1000)

    logger.info(f"Fetching {symbol} {timeframe} data from {start_time} to {end_time}")

    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Fetch data in chunks and write to CSV
    with output_file.open("w", newline="") as f:
        writer = csv.writer(f)
        # Write header matching our engine's expected format
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])

        current_start = start_ms
        total_intervals = (end_ms - start_ms) // interval_ms
        progress_bar = tqdm(total=total_intervals, desc=f"Fetching {symbol}")

        while current_start < end_ms:
            try:
                # Calculate chunk end (max 1000 klines per request)
                chunk_end = min(current_start + interval_ms * 1000, end_ms)

                # Fetch klines chunk
                if use_futures:
                    # Futures API uses different parameter names and format
                    klines = klines_func(
                        symbol=symbol,
                        interval=timeframe,
                        startTime=current_start,
                        endTime=chunk_end,
                        limit=1000,
                    )
                else:
                    klines = klines_func(
                        symbol,
                        timeframe,
                        start_str=str(current_start),
                        end_str=str(chunk_end),
                        limit=1000,
                    )

                if not klines:
                    logger.warning(
                        f"No data returned for chunk starting at {current_start}"
                    )
                    break

                # Write klines to CSV
                for kline in klines:
                    # Kline format: [timestamp, open, high, low, close, volume, ...]
                    writer.writerow(
                        [
                            iso_timestamp(kline[0]),  # timestamp
                            float(kline[1]),  # open
                            float(kline[2]),  # high
                            float(kline[3]),  # low
                            float(kline[4]),  # close
                            float(kline[5]),  # volume
                        ]
                    )

                # Update progress
                progress_bar.update(len(klines))

                # Move to next chunk - CRITICAL: always update even if we got same data
                if len(klines) > 0:
                    current_start = klines[-1][0] + interval_ms
                else:
                    # If no klines returned, move forward by our chunk size to avoid infinite loop
                    current_start = chunk_end

                # Rate limiting to avoid hitting API limits
                time.sleep(0.1)  # 100ms delay between requests

            except Exception as e:
                logger.error(f"Error fetching chunk starting at {current_start}: {e}")
                # CRITICAL: always advance current_start to avoid infinite loop
                current_start = chunk_end
                time.sleep(1)  # Wait longer on error

        progress_bar.close()

    logger.info(f"Successfully saved {output_file}")

    # Validate the output
    validate_csv_output(output_file)


def validate_csv_output(csv_file: Path) -> None:
    """Validate that the CSV file has the expected format and data quality."""
    import pandas as pd

    try:
        df = pd.read_csv(csv_file)
        logger.info(f"Validation: {len(df)} rows loaded")

        # Check required columns
        required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        missing_cols = set(required_columns) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Check for zero volume (data quality indicator)
        zero_volume_count = (df["volume"] == 0).sum()
        zero_volume_ratio = zero_volume_count / len(df)

        if zero_volume_ratio > 0.1:  # More than 10% zero volume
            logger.warning(
                f"High zero-volume ratio: {zero_volume_ratio:.1%} ({zero_volume_count}/{len(df)} rows). "
                f"This may indicate exchange maintenance periods or low liquidity."
            )
        else:
            logger.info(
                f"Good data quality: only {zero_volume_ratio:.1%} zero-volume bars"
            )

        # Check for gaps in timestamps
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        time_diffs = df["timestamp"].diff().dropna()

        # Detect significant gaps (more than 2x expected interval)
        expected_interval = (
            time_diffs.mode()[0] if not time_diffs.empty else pd.Timedelta(minutes=5)
        )
        large_gaps = time_diffs[time_diffs > expected_interval * 2]

        if len(large_gaps) > 0:
            logger.warning(
                f"Found {len(large_gaps)} time gaps larger than {expected_interval * 2}"
            )
        else:
            logger.info("No significant time gaps detected")

        # OHLC validation
        ohlc_issues = 0
        for _, row in df.head(1000).iterrows():  # Check first 1000 rows
            if not (
                row["low"] <= row["open"] <= row["high"]
                and row["low"] <= row["close"] <= row["high"]
            ):
                ohlc_issues += 1

        if ohlc_issues > 0:
            logger.warning(
                f"Found {ohlc_issues} OHLC validation issues in first 1000 rows"
            )
        else:
            logger.info("OHLC validation passed")

    except Exception as e:
        logger.error(f"Validation failed: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch historical data from Binance for backtesting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch 5-minute BTC data for 5 days from Futures
  python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-05-15T00:00:00 2025-05-20T00:00:00 --futures

  # Fetch 1-hour ETH data for a month from Spot
  python scripts/fetch_binance_klines.py ETHUSDT 1h 2025-01-01T00:00:00 2025-01-31T23:59:59

  # Fetch daily data with custom output path
  python scripts/fetch_binance_klines.py BTCUSDT 1d 2024-01-01T00:00:00 2024-12-31T23:59:59 --output data/btc_daily_2024.csv
        """,
    )

    parser.add_argument("symbol", help="Trading pair symbol (e.g., BTCUSDT, ETHUSDT)")
    parser.add_argument("timeframe", choices=list(TF_MAP.keys()), help="Kline interval")
    parser.add_argument(
        "start_time", help="Start time in ISO format (e.g., 2025-05-15T00:00:00)"
    )
    parser.add_argument(
        "end_time", help="End time in ISO format (e.g., 2025-05-20T00:00:00)"
    )

    parser.add_argument(
        "--futures", action="store_true", help="Use Futures API instead of Spot"
    )
    parser.add_argument(
        "--testnet", action="store_true", help="Use testnet (requires API keys)"
    )
    parser.add_argument("--output", "-o", type=Path, help="Output CSV file path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Generate output filename if not provided
    if args.output is None:
        date_str = args.start_time[:10]  # Extract YYYY-MM-DD
        market_type = "futures" if args.futures else "spot"
        args.output = Path(
            f"data/{args.symbol}_{args.timeframe}_{date_str}_{market_type}.csv"
        )

    # Fetch the data
    try:
        fetch_binance_data(
            symbol=args.symbol.upper(),
            timeframe=args.timeframe,
            start_time=args.start_time,
            end_time=args.end_time,
            output_file=args.output,
            use_futures=args.futures,
            testnet=args.testnet,
        )

        print(f"✅ Successfully fetched {args.symbol} data to {args.output}")

    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
