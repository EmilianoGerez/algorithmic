# Quant Algorithm Skeleton

Production-ready multi-timeframe liquidity pool strategy with HTF signal detection.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set up pre-commit hooks for code quality (recommended)
./setup-precommit.sh

# Run 5-minute BTC backtest with HTF liquidity strategy
.venv/bin/quantbt run data/BTC_USD_5min_20250728_021825.csv --config configs/base.yaml --plot

# Or use the legacy interface
python -m services.backtester --file sample_data/your_file.csv
```

## Features

✅ **HTF Liquidity Strategy**: Complete implementation with FVG detection, pool registry, and zone monitoring
✅ **Signal Pipeline**: FSM-driven candidate processing with EMA alignment and regime filtering
✅ **Risk Management**: ATR-based position sizing with 2:1 R/R ratios
✅ **Real-time Processing**: Sub-millisecond latency with memory-efficient design
✅ **Production Ready**: Comprehensive logging, metrics, and error handling

Next steps:

1. ✅ ~~Implement TimeAggregator inside `core/strategy`.~~
2. ✅ ~~Flesh out FVG & Pivot detectors.~~
3. ✅ ~~Build ZoneWatcher & FSM.~~
4. ✅ ~~Add broker integration in `infra/brokers`.~~

Refer to the `Quant Algorithm Platform – Technical Blueprint` notebook for full specs.

## Development

### Code Quality

This project uses automated code quality checks:

- **Pre-commit hooks**: Run `./setup-precommit.sh` to install (see [PRE-COMMIT.md](PRE-COMMIT.md))
- **Linting**: Ruff with auto-fixing
- **Formatting**: Ruff formatter
- **Type checking**: MyPy in strict mode
- **Testing**: Pytest with coverage

### Running Checks Manually

```bash
# All quality checks
.venv/bin/pre-commit run --all-files

# Individual tools
.venv/bin/ruff check . --fix
.venv/bin/ruff format .
.venv/bin/mypy core/ --strict
.venv/bin/pytest tests/ -v
```
