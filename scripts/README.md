# Scripts Directory

This directory contains utility scripts for data management and other tasks related to the algorithmic trading system.

## Available Scripts

### `fetch_crypto_data.py`

Fetches historical cryptocurrency data from Alpaca's API and saves it as CSV files suitable for backtesting.

#### Features

- Supports multiple crypto symbols (BTC/USD, ETH/USD, etc.)
- Multiple timeframes (1min, 5min, 15min, 30min, 1hour, 4hour, 1day)
- Automatic pagination handling for large data sets
- Rate limiting to respect API limits
- CSV output format compatible with backtesting system

#### Usage

```bash
# Basic usage - fetch BTC/USD 5-minute data
python scripts/fetch_crypto_data.py --symbol BTC/USD --timeframe 5min --start 2025-05-01 --end 2025-07-01

# Fetch ETH/USD daily data for a year
python scripts/fetch_crypto_data.py --symbol ETH/USD --timeframe 1day --start 2024-01-01 --end 2024-12-31

# Custom output directory
python scripts/fetch_crypto_data.py --symbol BTC/USD --timeframe 1hour --start 2025-06-01 --end 2025-06-30 --output historical_data
```

#### Parameters

- `--symbol`: Crypto symbol (e.g., BTC/USD, ETH/USD)
- `--timeframe`: Time frame (1min, 5min, 15min, 30min, 1hour, 4hour, 1day)
- `--start`: Start date in YYYY-MM-DD format
- `--end`: End date in YYYY-MM-DD format
- `--output`: Output directory (default: data)
- `--limit`: Records per API request (default: 10000, max: 10000)

#### Output Format

The script generates CSV files with the following columns:

- `timestamp`: ISO format timestamp
- `open`: Opening price
- `high`: Highest price
- `low`: Lowest price
- `close`: Closing price
- `volume`: Volume traded
- `vwap`: Volume weighted average price
- `trade_count`: Number of trades

### `example_fetch.py`

A simple example script demonstrating how to use the crypto data fetcher.

```bash
python scripts/example_fetch.py
```

### `validate_data.py`

Validates CSV data files to ensure they're properly formatted for backtesting.

```bash
# Validate a single file
python scripts/validate_data.py data/BTC_USD_5min_20250727_204942.csv

# Validate multiple files with summary statistics
python scripts/validate_data.py data/*.csv --summary
```

#### Features

- Validates required column headers
- Checks data format and types
- Validates OHLC price relationships
- Provides summary statistics (with --summary flag)
- Identifies common data quality issues

## Setup

1. Ensure you have the required dependencies installed:

   ```bash
   pip install -r requirements.txt
   ```

2. Set up your Alpaca API credentials in the `.env` file:

   ```
   ALPACA_API_KEY=your_api_key_here
   ALPACA_API_SECRET=your_api_secret_here
   ```

3. Run the scripts from the project root directory.

## API Requirements

- Valid Alpaca Markets account with API access
- API keys set in environment variables
- Respect for API rate limits (script includes automatic rate limiting)

## Notes

- The Alpaca crypto data API supports US crypto pairs
- Historical data availability may vary by symbol and timeframe
- Large date ranges may require multiple API calls due to pagination
- All timestamps are in UTC format
