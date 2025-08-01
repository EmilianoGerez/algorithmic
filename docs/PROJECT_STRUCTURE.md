# Project Structure Guide

This document describes the organized structure of the algorithmic trading platform after the comprehensive cleanup and reorganization.

## Directory Structure

```
algorithmic/
├── core/                          # Core Strategy Components
│   ├── clock.py                   # Simulation clock
│   ├── entities.py                # Trading entities (Candle, etc.)
│   ├── utils.py                   # Core utilities
│   ├── detectors/                 # Signal detection components
│   │   ├── fvg.py                # Fair Value Gap detector
│   │   ├── pivot.py              # Pivot point detector
│   │   ├── events.py             # Event definitions
│   │   └── manager.py            # Detector manager
│   ├── indicators/                # Technical indicators
│   │   ├── atr.py                # Average True Range
│   │   ├── ema.py                # Exponential Moving Average
│   │   ├── pack.py               # Indicator package
│   │   └── ...                   # Other indicators
│   ├── risk/                      # Risk management
│   │   ├── manager.py            # Risk manager
│   │   ├── config.py             # Risk configuration
│   │   └── live_reconciler.py    # Live trading reconciliation
│   ├── strategy/                  # Strategy components
│   │   ├── factory.py            # Strategy factory
│   │   ├── aggregator.py         # Time aggregation
│   │   ├── pool_manager.py       # Liquidity pool management
│   │   ├── zone_watcher.py       # Zone monitoring
│   │   └── ...                   # Other strategy components
│   └── trading/                   # Trading models
│       ├── models.py             # Trading data models
│       └── protocols.py          # Trading protocols
│
├── services/                      # Service Layer
│   ├── runner.py                 # Main backtest runner
│   ├── data_loader.py            # Data loading service
│   ├── metrics.py                # Metrics collection
│   ├── models.py                 # Service models
│   ├── replay.py                 # Replay engine
│   └── cli/                      # Command line interface
│       └── cli.py                # CLI implementation
│
├── infra/                         # Infrastructure Layer
│   ├── brokers/                  # Broker implementations
│   │   ├── broker.py             # Paper broker
│   │   ├── binance_futures.py    # Binance futures broker
│   │   ├── alpaca.py             # Alpaca broker
│   │   └── ...                   # Other brokers
│   └── data/                     # Data providers
│       └── providers.py          # Data provider implementations
│
├── scripts/                       # Utility Scripts (Organized)
│   ├── README.md                 # Scripts overview
│   ├── analysis/                 # Analysis and Research Tools
│   │   ├── README.md             # Analysis tools guide
│   │   ├── analyze_backtest.py   # Main backtest analysis
│   │   ├── investigate_may_20.py # Specific investigations
│   │   └── detailed_may_20_analysis.py
│   ├── debug/                    # Debugging Utilities
│   │   ├── README.md             # Debug tools guide
│   │   ├── debug_fvg.py          # FVG debugging
│   │   ├── debug_manager.py      # Manager debugging
│   │   ├── debug_pipeline.py     # Pipeline debugging
│   │   ├── trace_pipeline.py     # Pipeline tracing
│   │   └── ...                   # Other debug tools
│   ├── demos/                    # Demo and Example Scripts
│   │   ├── demo_phase1.py        # Phase 1 demonstration
│   │   ├── demo_phase2.py        # Phase 2 demonstration
│   │   ├── demo_enhanced.py      # Enhanced demo
│   │   ├── complete_enhanced_demo.py # Complete analysis demo
│   │   └── run_enhanced_analysis.py  # Interactive analysis
│   └── visualization/            # Plotting and Visualization
│       ├── README.md             # Visualization guide
│       ├── data_exporter.py      # Data export for visualization
│       ├── simple_plot.py        # Simple plotting utilities
│       └── ...                   # Other visualization tools
│
├── tests/                         # Test Suite
│   ├── integration/              # Integration tests
│   ├── unit/                     # Unit tests
│   ├── test_*.py                 # Test modules
│   └── ...                       # Other test files
│
├── docs/                          # Documentation
│   ├── PROJECT_STRUCTURE.md      # This file
│   ├── PROJECT_CLEANUP_SUMMARY.md # Cleanup summary
│   ├── BACKTEST_ANALYSIS.md      # Analysis tools guide
│   ├── ENHANCED_ANALYSIS_GUIDE.md # Enhanced analysis guide
│   ├── LIVE_TRADING_SETUP.md     # Live trading setup
│   ├── binance_data_guide.md     # Binance data integration
│   └── ...                       # Other documentation
│
├── configs/                       # Configuration Files
│   ├── base.yaml                 # Base configuration
│   ├── binance.yaml              # Binance-specific config
│   ├── walk_forward_test.yaml    # Walk-forward testing
│   └── sweeps/                   # Parameter sweep configs
│
├── data/                          # Data Storage
│   └── *.csv                     # Market data files
│
├── results/                       # Backtest Results
│   └── backtest_*/               # Individual backtest outputs
│
└── ...                           # Root level files
    ├── README.md                 # Main project documentation
    ├── requirements.txt          # Python dependencies
    ├── pyproject.toml           # Project configuration
    └── setup-precommit.sh      # Development setup script
```

## Key Directories Explained

### Core (`core/`)
Contains the fundamental trading strategy components that implement the HTF liquidity detection algorithm. This is the heart of the trading logic.

### Services (`services/`)
Provides the orchestration layer that coordinates strategy execution, data loading, and backtesting workflows.

### Infrastructure (`infra/`)
Handles external integrations like broker APIs and data providers. Designed for easy extension to new brokers.

### Scripts (`scripts/`)
Organized utility scripts by purpose:
- **Analysis**: Tools for analyzing backtest results and market data
- **Debug**: Utilities for debugging strategy components and pipeline issues
- **Demos**: Example scripts and demonstrations of functionality
- **Visualization**: Tools for creating charts and exporting data for analysis

### Tests (`tests/`)
Comprehensive test suite covering unit tests, integration tests, and acceptance tests.

### Docs (`docs/`)
All project documentation, guides, and technical specifications.

## Usage Examples

### Running Analysis Tools
```bash
# Analyze latest backtest results
python scripts/analysis/analyze_backtest.py

# Debug FVG detection
python scripts/debug/debug_fvg.py

# Run enhanced demo
python scripts/demos/demo_enhanced.py
```

### Key Benefits of This Structure

1. **Clear Separation of Concerns**: Each directory has a specific purpose
2. **Easy Navigation**: Logical grouping makes finding files intuitive
3. **Maintainability**: Related functionality is grouped together
4. **Scalability**: Easy to add new scripts in appropriate categories
5. **Documentation**: Each major directory has its own README

## Migration from Old Structure

The project was reorganized from a scattered structure with 80+ files in the root to this organized hierarchy. All import paths have been updated, and the functionality remains identical.

### Scripts That Moved:
- `analyze_backtest.py` → `scripts/analysis/analyze_backtest.py`
- `debug_*.py` → `scripts/debug/debug_*.py`
- `demo_*.py` → `scripts/demos/demo_*.py`
- Visualization tools → `scripts/visualization/`

All references in documentation and code have been updated to reflect the new structure.
