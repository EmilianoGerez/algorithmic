# 🚀 Algorithmic Trading System

![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

A comprehensive quantitative trading system with advanced optimization capabilities and real-time backtesting.

## 📁 Project Structure

```
algorithmic/
├── 🏗️ core/              # Core trading engine and strategy components
├── 🔧 services/          # Backend services (optimization, data, metrics)
├── 🛠️ tools/             # Utility tools and scripts
│   ├── optimization/     # Optimization runners and demos
│   ├── analysis/        # Performance analysis dashboards
│   └── monitoring/      # Live monitoring tools
├── ⚙️ configs/           # Configuration files
├── 📊 data/              # Market data files
├── 📖 docs/              # Documentation
├── 🧪 tests/             # Test configurations
├── 📈 results/           # Optimization and backtest results
└── 🎯 run_backtest.py    # Main backtest runner
```

## 🚀 Quick Start

### 1. Installation

```bash
# Set up environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Set up pre-commit hooks (recommended)
./setup-precommit.sh
```

### 2. Run a Backtest

```bash
# Using the CLI command
quantbt --config configs/optimized_btc_20250801.yaml

# Using the Python script
python run_backtest.py --config configs/optimized_btc_20250801.yaml

# Legacy interface
python -m services.backtester --file data/BTCUSDT_5m_2025-05-18_futures.csv
```

### 3. Run Optimization

```bash
# 3-phase optimization (recommended)
python tools/optimization/run_3phase_optimization.py --n1 25 --n2 25 --n3 50

# Quick optimization testing
python tools/optimization/run_ultra_fast_optimization.py
```

### 4. Analyze Results

```bash
# Generate performance dashboard
python tools/analysis/optimization_dashboard.py

# Monitor live optimization
python tools/monitoring/monitor_optimization_live.py
```

## Features

✅ **HTF Liquidity Strategy**: Complete implementation with FVG detection, pool registry, and zone monitoring
✅ **Signal Pipeline**: FSM-driven candidate processing with EMA alignment and regime filtering
✅ **Risk Management**: ATR-based position sizing with 2:1 R/R ratios
✅ **Real-time Processing**: Sub-millisecond latency with memory-efficient design
✅ **Production Ready**: Comprehensive logging, metrics, and error handling
✅ **Prometheus Metrics**: Built-in metrics endpoint for monitoring and observability

## Configuration

### Killzone Times

Killzone times in configuration are specified in **UTC format**:

```yaml
strategy:
  filters:
    killzone: ["01:00", "18:00"] # UTC times
```

**Market Session Mapping (UTC)**:

- **Asia Session**: 01:00-10:00 UTC (Tokyo: 10:00-19:00 JST)
- **London Session**: 08:00-17:00 UTC (London: 08:00-17:00 GMT/BST)
- **New York Session**: 13:00-22:00 UTC (New York: 08:00-17:00 EST/EDT)

**Common Killzone Configurations**:

- `["01:00", "18:00"]` - Asia start to NY end (covers all major sessions)
- `["08:00", "17:00"]` - London session only
- `["13:00", "22:00"]` - New York session only
- `["01:00", "10:00"]` - Asia session only

### Volume Filtering

The strategy automatically detects poor data quality and adjusts volume filtering:

```yaml
strategy:
  filters:
    volume_multiple: 0 # Auto-disabled when >30% zero-volume bars detected
```

**Volume Multiple Guidelines**:

- `0` - Disable volume filtering (recommended for synthetic/low-quality data)
- `1.5+` - Enable volume filtering (recommended for high-quality exchange data)

## Monitoring

### Prometheus Metrics

The platform exposes Prometheus-compatible metrics for monitoring:

- Pool registry statistics (created, active, touched pools)
- Trading performance metrics (PnL, trade counts, win rates)
- System performance (latency, memory usage, processing times)

Access metrics through the built-in endpoint or export to your monitoring stack.

Next steps:

1. ✅ ~~Implement TimeAggregator inside `core/strategy`.~~
2. ✅ ~~Flesh out FVG & Pivot detectors.~~
3. ✅ ~~Build ZoneWatcher & FSM.~~
4. ✅ ~~Add broker integration in `infra/brokers`.~~

Refer to the `Quant Algorithm Platform – Technical Blueprint` notebook for full specs.

## Development

### Project Structure

The project is organized for maintainability and clarity:

```
algorithmic/
├── core/              # Core strategy components
├── services/          # CLI, metrics, runner services
├── infra/            # Brokers, data providers
├── tests/            # All test files
├── scripts/          # Utility scripts (organized by purpose)
│   ├── analysis/     # Data analysis and backtest tools
│   ├── debug/        # Debugging utilities
│   ├── demos/        # Demo and example scripts
│   └── visualization/ # Plotting and charting
├── docs/             # Documentation
├── configs/          # Configuration files
└── data/             # Data storage
```

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
