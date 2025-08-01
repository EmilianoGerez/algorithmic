# Backtest Analysis Tools

Professional analysis tools for HTF Liquidity Strategy backtesting results.

## 🎯 Main Analysis Tool

### `scripts/analysis/analyze_backtest.py` - Professional Analysis Tool

The primary tool for comprehensive backtest analysis with enhanced visualizations.

#### Usage Examples:

```bash
# Analyze latest backtest results automatically
python3 scripts/analysis/analyze_backtest.py

# Analyze specific results folder
python3 scripts/analysis/analyze_backtest.py results/backtest_20250730_162303

# List all available backtest results
python3 scripts/analysis/analyze_backtest.py --list

# Analyze with specific export formats only
python3 scripts/analysis/analyze_backtest.py --formats csv json

# Run analysis without showing interactive plot
python3 scripts/analysis/analyze_backtest.py --no-plot

# Get full help
python3 scripts/analysis/analyze_backtest.py --help
```

#### Generated Outputs:

- **`enhanced_trading_plot.html`** - Interactive chart with SL/TP levels, entry/exit points
- **`trade_summary_TIMESTAMP.csv`** - Detailed trade data for Excel analysis
- **`trade_summary_TIMESTAMP.json`** - Structured data for further processing
- **`trade_summary_TIMESTAMP.xlsx`** - Excel workbook with summary statistics

## 🚀 Quick Helper

### `quick_analysis.py` - Interactive Helper

Simple interactive interface for users who prefer guided analysis.

```bash
python3 quick_analysis.py
```

This launches an interactive menu with options to:

1. Analyze latest results
2. List available results
3. Analyze specific folder
4. Show usage help

## 📊 What You Get

### Enhanced Visualizations:

- ✅ Interactive candlestick charts with volume
- ✅ Entry/exit points clearly marked
- ✅ Stop-loss levels (red dashed lines)
- ✅ Take-profit levels (green dotted lines)
- ✅ Risk-reward ratios displayed
- ✅ FVG zones visualization
- ✅ Position side color coding

### Comprehensive Trade Analysis:

- ✅ Win/loss statistics
- ✅ Risk-reward ratios per trade
- ✅ Portfolio performance metrics
- ✅ Trade duration analysis
- ✅ Commission/fee tracking
- ✅ Excel-ready summary sheets

## 🔧 Requirements

The analysis tools require these data files in the results folder:

- **`data.csv`** (required) - Market OHLCV data
- **`trades.json`** (optional) - Completed trades data
- **`open_positions.json`** (optional) - Current open positions
- **`events.parquet`** (optional) - FVG and other strategy events

## 📁 File Organization

```
results/
├── backtest_20250730_162303/     # ← Analyze this folder
│   ├── data.csv                  # Required
│   ├── trades.json               # Optional
│   ├── open_positions.json       # Optional
│   ├── events.parquet            # Optional
│   └── enhanced_trading_plot.html # Generated
└── backtest_20250730_162300/
    └── ...
```

## 🆚 Migration from Demo Scripts

**Old confusing demo scripts** (deprecated):

- ~~`complete_enhanced_demo.py`~~
- ~~`scripts/demos/demo_enhanced.py`~~
- ~~`run_enhanced_analysis.py`~~

**New professional tools**:

- `scripts/analysis/analyze_backtest.py` - Main analysis tool
- `quick_analysis.py` - Interactive helper

## 💡 Tips

1. **Latest Results**: Run `python3 scripts/analysis/analyze_backtest.py` without arguments to automatically use the most recent backtest
2. **List Results**: Use `--list` to see all available backtest folders with validation status
3. **Batch Analysis**: The tool validates directories and provides clear error messages for missing files
4. **Interactive Charts**: Open the generated HTML file in any browser for interactive analysis
5. **Excel Integration**: CSV exports are ready for immediate Excel import and pivot table analysis
