# Binance Data Quick Reference

## Common Commands

### Testing & Development

```bash
# Quick test (2 minutes)
python scripts/fetch_binance_klines.py BTCUSDT 1m 2025-07-29T12:00:00 2025-07-29T12:02:00

# Small development dataset (2 hours)
python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-07-28T12:00:00 2025-07-28T14:00:00 --futures
```

### Production Data

```bash
# 1 day of 5m Futures data
python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-07-28T00:00:00 2025-07-29T00:00:00 --futures

# 1 week of hourly data
python scripts/fetch_binance_klines.py ETHUSDT 1h 2025-07-22T00:00:00 2025-07-29T00:00:00

# Custom output path
python scripts/fetch_binance_klines.py BTCUSDT 5m 2025-07-28T00:00:00 2025-07-29T00:00:00 --output data/custom_name.csv
```

### Testing

```bash
# Fast mock tests (no network)
pytest test_binance_mock.py -v

# Integration tests (real API calls)
pytest test_binance_integration.py -v

# Single integration test
pytest test_binance_integration.py::TestBinanceDataIntegration::test_binance_data_fetch_and_validation -v
```

## Timeframes

- **1m, 3m, 5m, 15m, 30m** - Minutes
- **1h, 2h, 4h, 6h, 8h, 12h** - Hours
- **1d, 3d, 1w** - Days/Weeks
- **1M** - Monthly (approximate)

## Symbols

- **BTCUSDT** - Bitcoin
- **ETHUSDT** - Ethereum
- **BNBUSDT** - Binance Coin
- **ADAUSDT** - Cardano
- **SOLUSDT** - Solana

## Flags

- `--futures` - Use Futures API instead of Spot
- `--testnet` - Use testnet (requires API keys)
- `--output PATH` - Custom output file path
- `--verbose` - Detailed logging

## Expected Performance

- **2-10 minutes**: 2-5 seconds
- **1-2 hours**: 30-60 seconds
- **1 day**: 2-5 minutes
- **1 week**: 10+ minutes

## Data Quality Results

- **Zero-volume bars**: 0.0% (vs 48.6% in poor data)
- **Time gaps**: None detected
- **OHLC validation**: 100% pass rate
