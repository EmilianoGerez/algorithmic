# 🖥️ QuantBT Terminal User Interface (TUI) Guide

## 🎯 Overview

The QuantBT TUI provides a **user-friendly shell interface** for managing all trading tools and services without needing to remember command-line syntax or read extensive documentation.

## 🚀 Quick Start

### Installation

```bash
# Run the setup script
./setup_tui.sh

# Or install manually
pip install typer rich
```

### Launch Options

```bash
# Method 1: Direct launch (recommended)
python3 quantbt_tui.py

# Method 2: Use launcher (with dependency checking)
python3 launch_tui.py

# Method 3: Traditional CLI (still available)
python3 quantbt_simple.py
```

## 🎨 Interface Overview

The TUI provides a beautiful, organized interface with:

- **📋 Main Menu** - Navigate to different sections
- **🎨 Rich Formatting** - Tables, panels, and color coding
- **🔄 Loading Indicators** - Visual feedback for operations
- **📂 File Browsers** - Interactive file selection
- **✅ Status Messages** - Clear success/error feedback

## 📱 Main Menu Sections

### 1. 📊 Data Management

- **📥 Fetch Binance Data** - Interactive data downloading
- **✅ Validate Data Files** - Check data quality and format
- **📋 Data File Information** - View file statistics and metadata
- **📂 Browse Data Directory** - Explore data files with details
- **🗂️ List Available Data** - Overview of all market data

### 2. 🎯 Backtesting

- **🚀 Quick Backtest** - Run with default settings
- **⚙️ Custom Backtest** - Interactive parameter selection
- **🔄 Walk-Forward Analysis** - Multi-fold validation
- **📊 Batch Backtesting** - Multiple configuration testing
- **🎯 Live Trading Mode** - Real-time trading simulation
- **📈 View Recent Results** - Browse and analyze past runs

### 3. 🧠 Optimization

- **⚡ Ultra Fast Optimization** - Quick parameter testing
- **🎯 3-Phase Optimization** - Comprehensive optimization pipeline
- **🧠 Bayesian Optimization** - Advanced parameter tuning
- **📊 Production Optimization** - Full validation optimization
- **📈 View Optimization Status** - Monitor progress and results
- **🛑 Stop Running Optimization** - Process management

### 4. 📈 Analysis & Reports

- **📊 Optimization Dashboard** - Comprehensive performance analysis
- **📈 Performance Reports** - Detailed trading metrics
- **📋 Summary Statistics** - Quick performance overview
- **📊 Comparison Analysis** - Compare multiple strategies

### 5. 📉 Visualization

- **📈 Chart Generation** - Interactive price charts with trades
- **📊 Equity Curves** - Performance visualization
- **🎯 Trade Analysis** - Individual trade visualization
- **📊 Parameter Heatmaps** - Optimization result visualization

### 6. 📡 Monitoring

- **💻 System Status** - Health checks and environment info
- **🔄 Optimization Monitor** - Real-time optimization tracking
- **📊 Live Performance** - Real-time trading metrics
- **📈 Resource Usage** - System resource monitoring
- **🎯 Trading Status** - Live trading position monitoring

### 7. ⚙️ Configuration

- **📋 List Configurations** - Browse all config files
- **✅ Validate Config** - Check configuration syntax
- **📝 Create New Config** - Template-based config creation
- **📂 Browse Config Directory** - Explore configuration files
- **🔧 Edit Configuration** - Interactive config editing

### 8. 🛠️ Tools & Utilities

- **🧹 Cleanup** - Clear cache and temporary files
- **🔧 Debug Tools** - Diagnostic utilities
- **📊 Demo Scripts** - Example implementations
- **🧪 Test Suite** - Validation and testing tools

### 9. 📚 Help & Documentation

- **📖 User Guides** - Comprehensive documentation
- **💡 Quick Tips** - Usage tips and best practices
- **🎯 Examples** - Sample workflows and commands
- **🔧 Troubleshooting** - Common issues and solutions

## 🎪 Key Features

### Interactive File Selection

```
Available data files:
1. BTCUSDT_5m_2025-05-18_futures.csv
2. BTC_USD_5min_20250801_001617.csv
3. BTC_USD_5min_20250801_160031.csv
4. BTC_USD_5min_20250801_180943.csv

Select file to validate (1-4) or 'all': 1
```

### Visual Progress Indicators

```
🔄 Running ultra fast optimization with 50 trials...
⠋ Running: python3 tools/optimization/run_ultra_fast_optimization.py...
```

### Rich Information Display

```
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Option ┃ Description             ┃                                         ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
┃ 1      ┃ 📊 Data Management      ┃ Fetch, validate, and manage market data ┃
┃ 2      ┃ 🎯 Backtesting          ┃ Run backtests and walk-forward analysis ┃
└────────┴─────────────────────────┴─────────────────────────────────────────┘
```

### Smart Error Handling

```
❌ Error: Missing required dependencies: ['polars']
💡 Try: pip install polars
```

## 🔄 Workflow Examples

### Complete Data-to-Results Workflow

1. **Start TUI**: `python3 quantbt_tui.py`
2. **Fetch Data**: Menu 1 → Option 1 → Enter BTCUSDT, 5m, 7 days
3. **Validate Data**: Menu 1 → Option 2 → Select downloaded file
4. **Run Backtest**: Menu 2 → Option 1 → Select config → Generate plot
5. **Optimize**: Menu 3 → Option 2 → Run 3-phase optimization
6. **Analyze**: Menu 4 → Generate dashboard
7. **Monitor**: Menu 6 → View system status

### Quick Testing Workflow

1. **Start TUI**: `python3 quantbt_tui.py`
2. **Quick Optimization**: Menu 3 → Option 1 → 50 trials
3. **View Results**: Menu 3 → Option 5 → Check status
4. **Generate Report**: Menu 4 → Dashboard

### Configuration Management Workflow

1. **Start TUI**: `python3 quantbt_tui.py`
2. **List Configs**: Menu 7 → Option 1
3. **Validate Config**: Menu 7 → Option 2 → Select config
4. **Test Config**: Menu 2 → Option 1 → Use validated config

## 🎯 Advantages Over CLI

### Before (CLI)

```bash
# Need to remember commands and paths
python3 tools/optimization/run_3phase_optimization.py --n1 25 --n2 25 --n3 50
python3 tools/analysis/optimization_dashboard.py
python3 quantbt_simple.py data fetch BTCUSDT 5m --days 7
```

### After (TUI)

```
🎯 Main Menu → 3. Optimization → 2. 3-Phase → Enter 25/25/50
📈 Main Menu → 4. Analysis → Generate Dashboard
📊 Main Menu → 1. Data → 1. Fetch → BTCUSDT/5m/7
```

## 🔧 Technical Details

### Dependencies

- **Required**: `typer` (command framework)
- **Optional**: `rich` (beautiful formatting)
- **Fallback**: Works without rich with basic formatting

### Architecture

- **Single file**: `quantbt_tui.py` (self-contained)
- **Menu system**: Hierarchical navigation
- **Command integration**: Calls existing scripts and CLI
- **Error handling**: Graceful fallbacks and user feedback

### Performance

- **Fast startup**: Minimal imports and lazy loading
- **Memory efficient**: Streams large datasets
- **Responsive**: Non-blocking operations with progress indicators

## 🆘 Troubleshooting

### Common Issues

#### TUI Won't Start

```bash
# Check dependencies
python3 -c "import typer"
pip install typer rich

# Check file permissions
chmod +x quantbt_tui.py
```

#### Commands Fail

```bash
# Check if you're in the right directory
ls -la quantbt_tui.py

# Check Python version
python3 --version  # Should be 3.7+
```

#### Missing Scripts

```bash
# Ensure all project files are present
ls scripts/ tools/ services/
```

### Getting Help

1. **In TUI**: Menu 9 → Help & Documentation
2. **CLI Help**: `python3 quantbt_simple.py --help`
3. **System Status**: Menu 6 → Option 1
4. **Documentation**: `cat docs/ENHANCED_CLI_GUIDE.md`

## 🎉 Success Indicators

When the TUI is working correctly, you should see:

- ✅ Beautiful formatted menus with tables
- ✅ Responsive navigation (up/down menus)
- ✅ File listings with metadata
- ✅ Progress indicators during operations
- ✅ Clear success/error messages
- ✅ Data validation and system checks

## 🚀 Next Steps

1. **Explore**: Try each menu section
2. **Test**: Run a complete workflow
3. **Customize**: Modify configs through the TUI
4. **Monitor**: Use real-time monitoring features
5. **Optimize**: Run parameter optimization
6. **Analyze**: Generate performance reports

The TUI makes your powerful trading platform **accessible, intuitive, and enjoyable to use**! 🎯📈
