# Enhanced Trading Analysis - Usage Guide

## 🚀 Quick Start

The enhanced trading analysis provides comprehensive visualization and detailed trade summaries for your HTF Liquidity Strategy backtests.

## 📋 Usage Options

### 1. **Basic Usage (Latest Results)**

```bash
python3 scripts/demos/complete_enhanced_demo.py
```

This automatically uses the most recent backtest results.

### 2. **Specify Results Folder**

```bash
# Use specific backtest folder
python3 scripts/demos/complete_enhanced_demo.py results/backtest_20250730_162303

# Use any custom folder containing data.csv
python3 scripts/demos/complete_enhanced_demo.py /path/to/your/results
```

### 3. **List Available Results**

```bash
# See all available backtest directories
python3 scripts/demos/complete_enhanced_demo.py --list

# Or use the helper script
python3 scripts/demos/run_enhanced_analysis.py --list
```

### 4. **Interactive Helper**

```bash
# Run interactive helper for guided selection
python3 scripts/demos/run_enhanced_analysis.py
```

## 📊 What You Get

### Generated Files:

- **`enhanced_trading_plot.html`** - Interactive chart with SL/TP levels
- **`trade_summary_YYYYMMDD_HHMMSS.csv`** - Detailed trade data for Excel
- **`trade_summary_YYYYMMDD_HHMMSS.json`** - Structured data for programming
- **`trade_summary_YYYYMMDD_HHMMSS.xlsx`** - Excel with summary statistics

### Visualizations:

- ✅ Interactive candlestick chart with volume
- ✅ Entry points marked with diamond symbols
- ✅ Stop-loss levels (red dashed lines)
- ✅ Take-profit levels (green dotted lines)
- ✅ Risk-reward ratios displayed on hover
- ✅ Closed trades with entry/exit markers
- ✅ Open positions with SL/TP projections

### Analysis Data:

- ✅ Risk and reward calculations per trade
- ✅ Commission and slippage tracking
- ✅ Trade duration analysis
- ✅ Portfolio performance metrics
- ✅ Win rate and PnL statistics

## 🔍 Data Requirements

The analysis needs a results folder containing:

- **`data.csv`** (required) - Market data with OHLCV columns
- **`all_trades.json`** (optional) - Real trade data from backtest
- **`open_positions.json`** (optional) - Open positions data

If real trade data isn't available, the script will generate mock data for demonstration.

## 💡 Examples

### Real Backtest Data Results

```
📊 Found real trades data: 8 trades
💰 Portfolio Statistics:
   • Closed Trades PnL: $1,684.90
   • Win Rate: 100.0%
   • Average Risk/Reward: 2.00
```

### Mock Data for Open Positions

```
📈 Created 7 open positions
💰 Portfolio Statistics:
   • Open Positions Risk: $2,170.00
   • Total Reward Potential: $1,120.00
   • Average Risk/Reward: 0.52
```

## 🎯 Next Steps

1. **View Interactive Chart**: Open the `enhanced_trading_plot.html` in your browser
2. **Analyze in Excel**: Import the CSV file for detailed analysis
3. **Review Statistics**: Check the Excel summary sheet for key metrics
4. **Evaluate Performance**: Use the data to assess strategy effectiveness

## 🛠 Troubleshooting

### "Required data.csv not found"

- Ensure you're pointing to a valid backtest results folder
- Check that the folder contains `data.csv` with OHLCV market data

### "No backtest directories found"

- Run a backtest first to generate results
- Check that results are in the `results/` directory

### Import Errors

- Ensure you have installed: `pip install plotly openpyxl pandas`

## 📞 Help

For more options:

```bash
python3 scripts/demos/complete_enhanced_demo.py --help
python3 scripts/demos/run_enhanced_analysis.py --help
```
