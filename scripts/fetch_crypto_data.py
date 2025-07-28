#!/usr/bin/env python3
"""
Script to fetch historical crypto data from Alpaca API and save as CSV for backtesting.

Usage:
    python scripts/fetch_crypto_data.py --symbol BTC/USD --timeframe 5min --start 2025-05-01 --end 2025-07-01
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv


def load_environment() -> tuple[str, str]:
    """Load environment variables from .env file."""
    load_dotenv()
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")

    if not api_key or not api_secret:
        print("Error: ALPACA_API_KEY and ALPACA_API_SECRET must be set in .env file")
        sys.exit(1)

    return api_key, api_secret


def fetch_crypto_bars(
    symbol: str,
    timeframe: str,
    start: str,
    end: str,
    api_key: str,
    api_secret: str,
    limit: int = 10000,
) -> list[dict[str, float | str | int]]:
    """
    Fetch crypto bars from Alpaca API with pagination support.

    Args:
        symbol: Crypto symbol (e.g., 'BTC/USD')
        timeframe: Time frame (e.g., '1min', '5min', '1hour', '1day')
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format
        api_key: Alpaca API key
        api_secret: Alpaca API secret
        limit: Number of bars per request (max 10000)

    Returns:
        List of bar data dictionaries
    """
    base_url = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
    }

    all_bars = []
    next_page_token = None
    page_count = 0

    while True:
        page_count += 1
        print(f"Fetching page {page_count}...")

        # Build query parameters
        params: dict[str, str | int] = {
            "symbols": symbol,
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "limit": limit,
            "sort": "asc",
        }

        if next_page_token:
            params["page_token"] = next_page_token

        # Make API request
        try:
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()

            # Extract bars for the symbol
            symbol_bars = data.get("bars", {}).get(symbol, [])
            if symbol_bars:
                all_bars.extend(symbol_bars)
                print(f"  Retrieved {len(symbol_bars)} bars (total: {len(all_bars)})")
            else:
                print("  No bars found in this page")

            # Check for next page
            next_page_token = data.get("next_page_token")
            if not next_page_token:
                print("No more pages to fetch")
                break

            # Rate limiting - be nice to the API
            time.sleep(0.1)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Response content: {e.response.text}")
            sys.exit(1)

    print(f"Total bars fetched: {len(all_bars)}")
    return all_bars


def save_to_csv(
    bars: list[dict[str, float | str | int]],
    symbol: str,
    timeframe: str,
    output_dir: str = "data",
) -> str:
    """
    Save bar data to CSV file in a format suitable for backtesting.

    Args:
        bars: List of bar data dictionaries
        symbol: Crypto symbol
        timeframe: Time frame
        output_dir: Output directory for CSV file

    Returns:
        Path to the created CSV file
    """
    if not bars:
        print("No data to save")
        return ""

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Generate filename
    symbol_clean = symbol.replace("/", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{symbol_clean}_{timeframe}_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    # Write CSV file
    with open(filepath, "w", newline="") as csvfile:
        fieldnames = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
            "trade_count",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for bar in bars:
            writer.writerow(
                {
                    "timestamp": bar["t"],
                    "open": bar["o"],
                    "high": bar["h"],
                    "low": bar["l"],
                    "close": bar["c"],
                    "volume": bar["v"],
                    "vwap": bar["vw"],
                    "trade_count": bar["n"],
                }
            )

    print(f"Data saved to: {filepath}")
    return filepath


def validate_date(date_string: str) -> bool:
    """Validate date string format YYYY-MM-DD."""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def main() -> None:
    """Main function to handle CLI arguments and orchestrate data fetching."""
    parser = argparse.ArgumentParser(
        description="Fetch historical crypto data from Alpaca API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch BTC/USD 5-minute data for 2 months
  python scripts/fetch_crypto_data.py --symbol BTC/USD --timeframe 5min --start 2025-05-01 --end 2025-07-01

  # Fetch ETH/USD daily data for 1 year
  python scripts/fetch_crypto_data.py --symbol ETH/USD --timeframe 1day --start 2024-01-01 --end 2024-12-31

  # Fetch with custom output directory
  python scripts/fetch_crypto_data.py --symbol BTC/USD --timeframe 1hour --start 2025-06-01 --end 2025-06-30 --output historical_data
        """,
    )

    parser.add_argument(
        "--symbol", required=True, help="Crypto symbol (e.g., BTC/USD, ETH/USD)"
    )

    parser.add_argument(
        "--timeframe",
        required=True,
        choices=["1min", "5min", "15min", "30min", "1hour", "4hour", "1day"],
        help="Time frame for the data",
    )

    parser.add_argument(
        "--start", required=True, help="Start date in YYYY-MM-DD format"
    )

    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format")

    parser.add_argument(
        "--output", default="data", help="Output directory for CSV file (default: data)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Number of bars per API request (default: 10000, max: 10000)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not validate_date(args.start):
        print("Error: Start date must be in YYYY-MM-DD format")
        sys.exit(1)

    if not validate_date(args.end):
        print("Error: End date must be in YYYY-MM-DD format")
        sys.exit(1)

    if args.limit > 10000:
        print("Error: Limit cannot exceed 10000")
        sys.exit(1)

    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")

    if start_date >= end_date:
        print("Error: Start date must be before end date")
        sys.exit(1)

    print(
        f"Fetching {args.symbol} {args.timeframe} data from {args.start} to {args.end}"
    )

    # Load API credentials
    api_key, api_secret = load_environment()

    # Fetch data
    bars = fetch_crypto_bars(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=args.start,
        end=args.end,
        api_key=api_key,
        api_secret=api_secret,
        limit=args.limit,
    )

    # Save to CSV
    if bars:
        csv_path = save_to_csv(bars, args.symbol, args.timeframe, args.output)
        print(f"\nSuccess! Data saved to: {csv_path}")
        print(f"Total records: {len(bars)}")

        if bars:
            print(f"Date range: {bars[0]['t']} to {bars[-1]['t']}")
    else:
        print("No data was fetched")


if __name__ == "__main__":
    main()
