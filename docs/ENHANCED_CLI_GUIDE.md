# 🚀 Enhanced QuantBT CLI Guide

The Enhanced QuantBT CLI provides a comprehensive, user-friendly interface to access all trading platform capabilities without needing to read extensive documentation or execute isolated commands.

## 🎯 Quick Setup

```bash
# Run the enhanced setup script
./setup_enhanced_cli.sh

# Or manually:
pip install rich typer optuna plotly
python quantbt_enhanced.py --version
```

## 📋 Command Structure

The enhanced CLI organizes functionality into logical categories:

### 📊 Data Management (`data`)

```bash
# Fetch market data from Binance
quantbt-enhanced data fetch BTCUSDT 5m --days 7
quantbt-enhanced data fetch ETHUSDT 1h --start 2025-01-01 --end 2025-01-31 --futures

# Validate data quality
quantbt-enhanced data validate data/BTCUSDT_5m.csv

# Get data statistics
quantbt-enhanced data info data/BTCUSDT_5m.csv
```

### 🎯 Backtesting (`backtest`)

```bash
# Single backtest
quantbt-enhanced backtest run --data data/BTCUSDT_5m.csv --config configs/btc.yaml --plot

# Walk-forward analysis
quantbt-enhanced backtest walk-forward data/BTCUSDT_5m.csv --folds 6 --config configs/btc.yaml

# Live trading (testnet/paper)
quantbt-enhanced backtest live binance --config configs/btc.yaml
quantbt-enhanced backtest live alpaca --config configs/stocks.yaml
```

### 🧠 Optimization (`optimize`)

```bash
# Quick optimization testing
quantbt-enhanced optimize quick --trials 50 --jobs 4

# 3-phase optimization (recommended)
quantbt-enhanced optimize 3phase --n1 25 --n2 25 --n3 50

# Bayesian optimization
quantbt-enhanced optimize bayesian --trials 200 --timeout 3600

# Grid search
quantbt-enhanced optimize grid configs/sweeps/risk_params.yaml
```

### 📊 Analysis (`analyze`)

```bash
# Comprehensive optimization dashboard
quantbt-enhanced analyze dashboard --results results/

# Performance analysis
quantbt-enhanced analyze performance --results results/ --detailed

# Individual backtest analysis
quantbt-enhanced analyze backtest results/backtest_20250806_160928/result.json
```

### 📈 Visualization (`visualize`)

```bash
# Interactive trading charts
quantbt-enhanced visualize chart data/BTCUSDT_5m.csv --trades results/trades.csv

# Equity curve plots
quantbt-enhanced visualize equity results/backtest_result.json
```

### 📡 Monitoring (`monitor`)

```bash
# Live optimization monitoring
quantbt-enhanced monitor optimization --results results/ --refresh 5

# System health check
quantbt-enhanced monitor system
```

### ⚙️ Configuration (`config`)

```bash
# Validate configuration
quantbt-enhanced config validate configs/btc.yaml

# List available configs
quantbt-enhanced config list

# Generate template
quantbt-enhanced config template --strategy htf --output my_config.yaml
```

### 🛠️ Tools (`tools`)

```bash
# Run demos
quantbt-enhanced tools demo --phase 1

# Debug components
quantbt-enhanced tools debug fvg --verbose
quantbt-enhanced tools debug fsm

# System cleanup
quantbt-enhanced tools cleanup --cache --temp
```

## 🎨 Features

### Rich Terminal Interface

- **Colored output** with status indicators
- **Tables and panels** for organized information
- **Progress indicators** for long-running operations
- **Interactive help** with examples

### Comprehensive Coverage

- **All existing tools** accessible through organized commands
- **Smart defaults** for common operations
- **Batch operations** for efficiency
- **Error handling** with helpful messages

### Integration Benefits

- **No documentation reading** required for basic operations
- **Consistent interface** across all tools
- **Parameter validation** and suggestions
- **Automatic dependency checking**

## 🔧 Advanced Usage

### Chaining Operations

```bash
# Fetch data → validate → run backtest → analyze
quantbt-enhanced data fetch BTCUSDT 5m --days 30
quantbt-enhanced data validate data/BTCUSDT_5m_*.csv
quantbt-enhanced backtest run --data data/BTCUSDT_5m_*.csv --plot
quantbt-enhanced analyze backtest results/latest/result.json
```

### Optimization Workflows

```bash
# Complete optimization workflow
quantbt-enhanced optimize 3phase --n1 50 --n2 50 --n3 100
quantbt-enhanced analyze dashboard
quantbt-enhanced monitor optimization &  # Background monitoring
```

### Live Trading Setup

```bash
# System check → config validation → live trading
quantbt-enhanced monitor system
quantbt-enhanced config validate configs/production.yaml
quantbt-enhanced backtest live binance --config configs/production.yaml
```

## 📖 Help System

Every command includes comprehensive help:

```bash
quantbt-enhanced --help                    # Main help
quantbt-enhanced data --help               # Category help
quantbt-enhanced data fetch --help         # Command help
```

## 🎯 Common Workflows

### Daily Trading Routine

1. **System Check**: `quantbt-enhanced monitor system`
2. **Data Update**: `quantbt-enhanced data fetch BTCUSDT 5m --days 1`
3. **Quick Test**: `quantbt-enhanced backtest run --plot`
4. **Live Trading**: `quantbt-enhanced backtest live binance`

### Strategy Development

1. **Template Config**: `quantbt-enhanced config template --strategy htf`
2. **Data Preparation**: `quantbt-enhanced data fetch SYMBOL 5m --days 90`
3. **Initial Backtest**: `quantbt-enhanced backtest run --plot`
4. **Optimization**: `quantbt-enhanced optimize quick --trials 100`
5. **Validation**: `quantbt-enhanced backtest walk-forward --folds 6`
6. **Analysis**: `quantbt-enhanced analyze dashboard`

### Research & Analysis

1. **Historical Data**: `quantbt-enhanced data fetch SYMBOL 1h --start 2024-01-01 --end 2024-12-31`
2. **Bulk Analysis**: `quantbt-enhanced optimize 3phase --n1 100 --n2 100 --n3 200`
3. **Comprehensive Report**: `quantbt-enhanced analyze performance --detailed`
4. **Visualization**: `quantbt-enhanced visualize chart data/SYMBOL_1h.csv`

## 🔄 Migration from Old CLI

The enhanced CLI is fully compatible with existing configurations and data:

```bash
# Old way
python run_backtest.py --config configs/btc.yaml --data data/BTCUSDT_5m.csv
python tools/optimization/run_3phase_optimization.py --n1 25 --n2 25 --n3 50

# New way (same functionality, better UX)
quantbt-enhanced backtest run --config configs/btc.yaml --data data/BTCUSDT_5m.csv
quantbt-enhanced optimize 3phase --n1 25 --n2 25 --n3 50
```

## 🎪 Interactive Features

The enhanced CLI provides immediate feedback and guidance:

- **Welcome panel** showing available commands
- **System status** with dependency checks
- **Progress indicators** for long operations
- **Success/error messages** with actionable advice
- **Parameter suggestions** for optimal performance

## 🚀 Getting Started

1. **Install**: Run `./setup_enhanced_cli.sh`
2. **Welcome**: Run `quantbt-enhanced` (no arguments)
3. **First test**: `quantbt-enhanced monitor system`
4. **Fetch data**: `quantbt-enhanced data fetch BTCUSDT 5m --days 7`
5. **Run backtest**: `quantbt-enhanced backtest run --plot`

The enhanced CLI transforms the complex trading platform into an intuitive, discoverable interface that guides users through all capabilities without requiring extensive documentation reading.
