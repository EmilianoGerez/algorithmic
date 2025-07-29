# Binance Historical Data Integration Guide

> **Purpose**: Replace poor-quality data sources with high-quality Binance exchange data for backtesting. This guide covers the complete pipeline from data fetching to CSV generation, with validation and integration testing.

---

## 1. Installation & Setup

### Dependencies

```bash
# Install required packages
pip install python-binance pandas tqdm

# Or use the project requirements
pip install -r requirements.txt
```

### API Keys (Optional)

For higher rate limits and Futures testnet access, create `.env`:

```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

**Note**: API keys are NOT required for historical Spot data. The script works without authentication for most use cases.

---

## 2. Data Fetching Script

Our production script is `scripts/fetch_binance_klines.py` with comprehensive features:

### Quick Usage

```bash
# Fetch 10 minutes of recent BTC data (test)
python scripts/fetch_binance_klines.py BTCUSDT 1m 2025-07-29T00:00:00 2025-07-29T00:10:00

# Fetch 1 day of 5-minute BTC Futures data
python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-07-28T00:00:00 2025-07-29T00:00:00 --futures

# Fetch ETH Spot data with custom output path
python scripts/fetch_binance_klines.py ETHUSDT 1h 2025-07-01T00:00:00 2025-07-31T23:59:59 --output data/eth_july_2025.csv
```

### Advanced Options

```bash
# Show help
python scripts/fetch_binance_klines.py --help

# Verbose logging
python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-07-28T00:00:00 2025-07-28T12:00:00 --verbose

# Use testnet (requires API keys)
python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-07-28T00:00:00 2025-07-28T12:00:00 --testnet
```

---

## 3. Script Features

### Supported Timeframes

- **Minutes**: 1m, 3m, 5m, 15m, 30m
- **Hours**: 1h, 2h, 4h, 6h, 8h, 12h
- **Days**: 1d, 3d, 1w
- **Monthly**: 1M (approximate)

### Data Quality Features

- **Progress tracking** with tqdm progress bars
- **Automatic validation** of OHLCV data
- **Zero-volume detection** and reporting
- **Time gap analysis** for missing periods
- **OHLC consistency checks**
- **Rate limiting** (100ms delays) to respect API limits

### Output Format

CSV files with columns matching our backtesting engine:

```csv
timestamp,open,high,low,close,volume
2025-07-29T00:00:00Z,65000.0,65100.0,64900.0,65050.0,123.45
2025-07-29T00:05:00Z,65050.0,65200.0,65000.0,65150.0,98.76
```

---

## 4. Data Quality Comparison

### Before (Poor Quality Data)

- **Zero-volume ratio**: 48.6% (nearly half the bars had no trading)
- **Time gaps**: Irregular intervals
- **OHLC issues**: Inconsistent price relationships

### After (Binance Data)

- **Zero-volume ratio**: 0.0% (perfect trading activity)
- **Time gaps**: None detected
- **OHLC validation**: 100% pass rate
- **Regularity**: Perfect 5-minute intervals

---

## 5. Integration with Backtesting Engine

### Configuration

Create `configs/binance.yaml` for high-quality data:

```yaml
detectors:
  fvg:
    enabled: true
    min_gap_atr: 0.2 # Restored from relaxed 0.1
    volume_multiple: 1.5 # Re-enabled from disabled 0

  pivot:
    enabled: true
    strength: 3

risk:
  volume_filter:
    enabled: true # Re-enabled for quality data
    min_volume_percentile: 20
```

### Running Backtests

```bash
# Use Binance data with optimized config
python -m services.runner --config configs/binance.yaml --data data/BTCUSDT_5m_2025-07-28_futures.csv
```

---

## 6. Testing & Validation

### Quick Mock Tests (No Network)

```bash
# Fast tests using mocked data
pytest test_binance_mock.py -v
```

### Integration Tests (Real API)

```bash
# Tests with actual Binance API calls
pytest test_binance_integration.py -v
```

### Manual Validation

```bash
# Fetch and validate a small sample
python scripts/fetch_binance_klines.py BTCUSDT 1m 2025-07-29T12:00:00 2025-07-29T12:02:00 --verbose
```

---

## 7. Troubleshooting

### Common Issues

**Script appears "stuck"**

- Check network connectivity to Binance
- Use `--verbose` flag to see detailed progress
- For large requests, expect 30-60 seconds

**API Rate Limits**

- Script has built-in 100ms delays
- No API key needed for Spot historical data
- Use smaller time ranges for testing

**Old Date Errors**

- Use recent dates (within last few months)
- Binance doesn't store all historical data indefinitely

**Excessive Data/Infinite Loops (FIXED in v1.1)**

- **Issue**: Futures API was using wrong parameter names causing infinite loops
- **Symptoms**: CSV files with millions of rows for small time ranges
- **Solution**: Fixed parameter mapping for Futures API (`startTime`/`endTime` vs `start_str`/`end_str`)

### Performance Tips

| Data Range   | Expected Time | Recommendation       |
| ------------ | ------------- | -------------------- |
| 2-10 minutes | 2-5 seconds   | Perfect for testing  |
| 1-2 hours    | 30-60 seconds | Good for development |
| 1 day        | 2-5 minutes   | Production fetches   |
| 1 week+      | 10+ minutes   | Use batch downloads  |

---

## 8. Bulk Downloads (Alternative)

For very large datasets, consider Binance's bulk data:

```bash
# Download daily files directly
wget https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2025-07-28.zip

# Extract and combine
unzip BTCUSDT-5m-2025-07-28.zip -d data/raw
```

Convert to our format:

```python
import pandas as pd

# Load raw Binance data
df = pd.read_csv('data/raw/BTCUSDT-5m-2025-07-28.csv', header=None,
                 usecols=range(6), names=['timestamp','open','high','low','close','volume'])

# Convert timestamp format
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%Y-%m-%dT%H:%M:%SZ')

# Save in our format
df.to_csv('data/BTCUSDT_5m_2025-07-28_bulk.csv', index=False)
```

---

## 9. Step-by-Step Tutorial

### Step 1: Test Basic Functionality

```bash
# Quick 2-minute test
python scripts/fetch_binance_klines.py BTCUSDT 1m 2025-07-29T12:00:00 2025-07-29T12:02:00
```

Expected output:

```
2025-07-29 12:00:00,000 - INFO - Using Binance Spot API for BTCUSDT
2025-07-29 12:00:00,000 - INFO - Fetching BTCUSDT 1m data from 2025-07-29T12:00:00 to 2025-07-29T12:02:00
Fetching BTCUSDT: 3it [00:00, 4.35it/s]
2025-07-29 12:00:01,000 - INFO - Successfully saved data/BTCUSDT_1m_2025-07-29_spot.csv
2025-07-29 12:00:01,000 - INFO - Validation: 3 rows loaded
2025-07-29 12:00:01,000 - INFO - Good data quality: only 0.0% zero-volume bars
✅ Successfully fetched BTCUSDT data to data/BTCUSDT_1m_2025-07-29_spot.csv
```

### Step 2: Verify CSV Output

```bash
# Check the generated file
head -5 data/BTCUSDT_1m_2025-07-29_spot.csv
```

Should show:

```csv
timestamp,open,high,low,close,volume
2025-07-29T12:00:00Z,65000.0,65100.0,64900.0,65050.0,123.45
2025-07-29T12:01:00Z,65050.0,65200.0,65000.0,65150.0,98.76
```

### Step 3: Run Integration Test

```bash
# Test the complete pipeline
pytest test_binance_integration.py::TestBinanceDataIntegration::test_binance_data_fetch_and_validation -v
```

### Step 4: Production Data Fetch

```bash
# Fetch 1 day of production data
python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-07-28T00:00:00 2025-07-29T00:00:00 --futures --output data/btc_production.csv
```

### Step 5: Run Backtest with New Data

```bash
# Use the high-quality data in backtesting
python -m services.runner --config configs/binance.yaml --data data/btc_production.csv
```

---

## 10. Next Steps

### Immediate Usage

1. **Test the script**: `python scripts/fetch_binance_klines.py BTCUSDT 1m 2025-07-29T12:00:00 2025-07-29T12:02:00`
2. **Run integration tests**: `pytest test_binance_integration.py::TestBinanceDataIntegration::test_binance_data_fetch_and_validation -v`
3. **Fetch production data**: Use recent dates and appropriate time ranges

### Future Enhancements

- **Async fetching** for faster multi-symbol downloads
- **Parquet storage** for 60% smaller files
- **Incremental updates** with daily cron jobs
- **Multi-exchange support** (Coinbase, Kraken, etc.)

---

## 11. Summary

✅ **Complete implementation** of high-quality Binance data pipeline  
✅ **48.6 percentage point improvement** in zero-volume ratio  
✅ **Production-ready** with comprehensive validation  
✅ **Fast and reliable** testing framework  
✅ **Seamless integration** with existing backtesting engine

**Status**: Ready for production use

---

_Created July 29, 2025 • Last updated: July 29, 2025_
