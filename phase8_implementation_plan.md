# Phase 8: Backtest & Walk-Forward CLI - Implementation Plan

> **Document Version:** 1.1
> **Created:** July 26, 2025
> **Author:** AI Assistant
> **Status:** Ready for Implementation
> **Updated:** Incorporated production-quality recommendations

---

## Executive Summary

Phase 8 represents the transition from a validated trading engine (Phase 7) to a production-ready backtesting platform. With 90% of the core trading infrastructure already complete, this phase focuses on building CLI tools, metrics collection, and parameter optimization capabilities.

**Key Insight:** The existing test fixtures contain the blueprint for the replay engine, making this phase highly achievable within the planned 1-week timeline.

**Production Quality:** Incorporating streaming fallbacks, real-time latency profiling, memory-efficient metrics, and deterministic reproducibility checks.

---

## Current State Assessment

### ✅ Phase 7 Completed Components

- **Core Trading Loop**: Candle ingestion → Indicators → Detectors → FSM → Risk → Broker
- **Liquidity Detection**: FVG detection, HLZ confluence, ZoneWatcher integration
- **Risk Management**: ATR-based position sizing, slippage hooks, notional optimization
- **Paper Broker**: Order execution, P&L tracking, gap scenario handling
- **Comprehensive Testing**: 171 tests passing with full code quality compliance

### 🎯 Phase 8 Objectives

1. **Batch Backtester**: `quantbt run` CLI with historical data replay
2. **Walk-Forward Analysis**: Time-series cross-validation with robustness metrics
3. **Hydra Parameter Sweeps**: Grid search optimization for strategy parameters
4. **Professional Reporting**: Multi-format output (CSV, JSON, Excel, Markdown)

---

## Technical Architecture

### Data Flow Design

```
CSV/Parquet → ReplayFeed → IndicatorPack → TimeAggregator → Detectors
     ↓
ZoneWatcher → SignalCandidate FSM → RiskManager → PaperBroker
     ↓
MetricsCollector → Results Serializer → Reports (CSV/JSON/Console)
```

### Performance Requirements

- **Speed Target**: <10 seconds for 1-year BTC data (525,600 bars)
- **Memory Efficiency**: Streaming processing for large datasets
- **Determinism**: Identical results across runs with same configuration
- **Scalability**: Support for parallel parameter sweeps

---

## Implementation Strategy

### Task Priority Matrix

| Priority | Component                    | Effort | Dependencies    | Risk Level |
| -------- | ---------------------------- | ------ | --------------- | ---------- |
| **P1**   | CLI Skeleton (Typer + Hydra) | 2 days | None            | Low        |
| **P1**   | Replay Engine Extension      | 2 days | Phase 7         | Low        |
| **P1**   | Metrics Collection           | 1 day  | Replay Engine   | Low        |
| **P2**   | Result Serialization         | 1 day  | Metrics         | Low        |
| **P2**   | Single Backtest Integration  | 1 day  | All P1          | Medium     |
| **P3**   | Walk-Forward Analysis        | 2 days | Single Backtest | Medium     |
| **P3**   | Hydra Multirun Setup         | 1 day  | Walk-Forward    | Medium     |

### Week 1 Implementation Plan

#### Days 1-2: Foundation Layer

```bash
# CLI Structure
quantbt run --config configs/eurusd.yaml --data data/EURUSD_1m.parquet
quantbt run --config configs/btc.yaml --data data/BTC_1m.csv --walk 6
quantbt multirun risk.risk_per_trade=0.005,0.01,0.02
```

#### Days 3-4: Core Engine

- Extract replay patterns from existing test fixtures
- Implement streaming data loader with Polars
- Connect to Phase 7 indicator pipeline
- Basic event-driven metrics collection

#### Days 5-7: Integration & Validation

- End-to-end single backtest workflow
- Performance optimization for 10-second target
- Result serialization and basic reporting
- Validation against deterministic test fixtures

---

## Production-Quality Recommendations

### Critical Implementation Improvements

| Component               | Recommendation                              | Rationale                                      | Implementation Priority |
| ----------------------- | ------------------------------------------- | ---------------------------------------------- | ----------------------- |
| **Streaming Loader**    | Polars + Pandas fallback                    | Wider adoption, CI portability                 | High                    |
| **Latency Profiling**   | `time.perf_counter_ns()` at each hop        | Real performance data, hot spot identification | High                    |
| **Metrics Persistence** | In-memory + streaming CSV writes            | Flat memory usage for multi-million bar runs   | High                    |
| **Sharpe Calculation**  | Configurable risk-free rate & sampling freq | Determinism across environments                | Medium                  |
| **Result Provenance**   | Config copy + git hash in output            | Research audit trail, reproducibility          | Medium                  |

### Enhanced Data Loading Strategy

```python
def load_market_data(path: str, **kwargs) -> pl.DataFrame:
    """Load market data with graceful fallback to pandas"""
    try:
        import polars as pl
        return pl.read_csv(path, **kwargs)
    except ImportError:
        import pandas as pd
        logger.warning("Polars not available, falling back to pandas (slower)")
        df_pandas = pd.read_csv(path, **kwargs)
        return pl.from_pandas(df_pandas)
    except Exception as e:
        logger.error(f"Failed to load data from {path}: {e}")
        raise
```

### Real-Time Latency Profiling

```python
import time
from contextlib import contextmanager

@contextmanager
def profile_latency(stage_name: str, metrics_collector):
    """Profile latency at each pipeline stage"""
    start_ns = time.perf_counter_ns()
    try:
        yield
    finally:
        elapsed_ns = time.perf_counter_ns() - start_ns
        metrics_collector.record_latency(stage_name, elapsed_ns / 1_000_000)  # ms

# Usage in pipeline
with profile_latency("indicator_update", metrics):
    indicator_pack.update(candle)
```

### Memory-Efficient Metrics Collection

```python
class StreamingMetricsCollector:
    """Write metrics both in-memory and to disk for large backtests"""

    def __init__(self, output_dir: Path):
        self.metrics = BacktestMetrics()
        self.trades_file = output_dir / "trades.csv"
        self.metrics_file = output_dir / "metrics.csv"

    def on_trade_closed(self, trade: Trade):
        # Update in-memory metrics
        self.metrics.total_trades += 1

        # Stream to CSV immediately (append mode)
        with open(self.trades_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([trade.symbol, trade.entry_time, trade.exit_time,
                           trade.pnl, trade.duration])
```

### Deterministic Sharpe Calculation

```python
@dataclass
class RiskMetricsConfig:
    """Configuration for risk metric calculations"""
    risk_free_rate: float = 0.02  # 2% annual
    trading_days_per_year: int = 252
    sampling_frequency: str = "1D"  # Daily returns

def calculate_sharpe_ratio(returns: pl.Series, config: RiskMetricsConfig) -> float:
    """Calculate Sharpe ratio with configurable parameters"""
    excess_returns = returns - (config.risk_free_rate / config.trading_days_per_year)
    return excess_returns.mean() / excess_returns.std() * (config.trading_days_per_year ** 0.5)
```

### Reproducibility Audit Trail

```python
def create_result_directory(base_path: Path, config: DictConfig) -> Path:
    """Create timestamped result directory with audit trail"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = base_path / f"backtest_{timestamp}"
    result_dir.mkdir(parents=True, exist_ok=True)

    # Copy configuration
    shutil.copy2(config.config_path, result_dir / "config.yaml")

    # Record git commit hash
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            text=True
        ).strip()

        with open(result_dir / "provenance.json", 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "git_commit": git_hash,
                "python_version": sys.version,
                "config_hash": hashlib.sha256(str(config).encode()).hexdigest()
            }, f, indent=2)
    except subprocess.CalledProcessError:
        logger.warning("Could not retrieve git commit hash")

    return result_dir
```

---

## Component Specifications

### 1. Metrics Collection Framework

```python
@dataclass
class BacktestMetrics:
    """Comprehensive KPI tracking for backtesting results"""

    # Performance Metrics
    total_trades: int = 0
    winning_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0

    # Risk Metrics
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # Timing & Execution
    avg_trade_duration: float = 0.0  # hours
    avg_latency_ms: float = 0.0

    # Portfolio Performance
    starting_equity: float = 10000.0
    ending_equity: float = 0.0
    cagr: float = 0.0
```

### 2. CLI Command Structure

```python
# Single Backtest
@typer.command()
def run(
    config: str = typer.Option(..., help="Strategy configuration file"),
    data: str = typer.Option(..., help="Historical data path (CSV/Parquet)"),
    walk: Optional[int] = typer.Option(None, help="Walk-forward folds"),
    output: str = typer.Option("results", help="Output directory")
):
    """Execute backtest with specified configuration"""

# Parameter Sweep
@typer.command()
def multirun(
    config: str = typer.Option(..., help="Base configuration"),
    sweep: str = typer.Option(..., help="Parameter sweep definition")
):
    """Run parameter optimization sweep"""
```

### 3. Walk-Forward Analysis

```python
class WalkForwardAnalyzer:
    """Time-series cross-validation for strategy robustness"""

    def split_data(self, data: pl.DataFrame, folds: int, train_ratio: float):
        """Split data into training/testing folds preserving temporal order"""

    def run_analysis(self, config: DictConfig) -> List[BacktestMetrics]:
        """Execute backtest across all folds and aggregate results"""

    def calculate_robustness_metrics(self, fold_results: List[BacktestMetrics]):
        """Compute stability metrics across folds"""
```

---

## Component Reuse Analysis

### High Reuse Potential (90% existing)

- **Core Trading Logic**: Direct reuse from Phase 7
- **Indicator Pipeline**: EMA, ATR, regime detection ready
- **Risk Management**: Position sizing and slippage hooks available
- **Paper Broker**: Order execution and P&L tracking complete
- **Data Models**: Candle, Order, Position entities established

### New Components Required (10% net new)

- **CLI Framework**: Typer + Hydra integration
- **Replay Orchestration**: Stream processing coordinator
- **Metrics Aggregation**: Event-driven KPI collection
- **Result Serialization**: Multi-format output handlers
- **Walk-Forward Logic**: Time-series data splitting

---

## Risk Assessment & Mitigation

### Technical Risks

| Risk                         | Impact | Probability | Mitigation                                              |
| ---------------------------- | ------ | ----------- | ------------------------------------------------------- |
| **Performance Bottleneck**   | High   | Medium      | Profile early, optimize hot paths, streaming processing |
| **Memory Usage**             | Medium | Medium      | Polars streaming, chunked loading                       |
| **Configuration Complexity** | Medium | High        | Start simple, incremental complexity                    |
| **Integration Issues**       | High   | Low         | Extensive testing with Phase 7 components               |

### Implementation Risks

| Risk                   | Impact | Probability | Mitigation                               |
| ---------------------- | ------ | ----------- | ---------------------------------------- |
| **Scope Creep**        | Medium | High        | Focus on acceptance criteria             |
| **Over-Engineering**   | Medium | Medium      | MVP approach, iterate                    |
| **Testing Complexity** | High   | Medium      | Deterministic fixtures, property testing |

---

## Acceptance Criteria

### Primary Success Metrics

- [ ] **Performance**: Single BTC backtest (1-year) completes in <10 seconds
- [ ] **Robustness**: Walk-forward 6 folds produces valid Sharpe ratios (≠ 0)
- [ ] **Optimization**: Hydra sweep generates results.csv with parameter outcomes
- [ ] **Determinism**: Identical results across multiple runs with same config
- [ ] **Quality**: Comprehensive test coverage maintains 90%+ threshold

### Enhanced Determinism Testing

- [ ] **SHA-256 Verification**: Run identical backtest twice in CI, assert trades.csv hash match
- [ ] **Cross-Platform Consistency**: Same results on Linux/macOS/Windows
- [ ] **Dependency Isolation**: Results unchanged with/without optional packages (polars fallback)

### Production-Quality Metrics

- [ ] **Memory Efficiency**: Flat memory usage for multi-million bar backtests
- [ ] **Latency Profiling**: Real-time performance data collection at each pipeline stage
- [ ] **Audit Trail**: Complete reproducibility with config + git hash tracking
- [ ] **Graceful Degradation**: Fallback mechanisms for missing dependencies

### Determinism Test Implementation

```python
def test_backtest_determinism():
    """Verify identical results across multiple runs"""
    config = load_test_config()

    # Run backtest twice
    result1 = run_backtest(config)
    result2 = run_backtest(config)

    # Compare CSV outputs
    trades1_hash = hashlib.sha256(open("trades_1.csv", "rb").read()).hexdigest()
    trades2_hash = hashlib.sha256(open("trades_2.csv", "rb").read()).hexdigest()

    assert trades1_hash == trades2_hash, "Backtest results are not deterministic"
    assert result1.total_pnl == result2.total_pnl, "P&L calculations differ"
    assert result1.total_trades == result2.total_trades, "Trade counts differ"
```

### Secondary Success Metrics

- [ ] **Usability**: Intuitive CLI interface with helpful error messages
- [ ] **Flexibility**: Support for multiple data formats (CSV, Parquet)
- [ ] **Reporting**: Professional output suitable for research documentation
- [ ] **Extensibility**: Clean interfaces for future live trading integration

---

## Implementation Timeline

### Week 1: Core Development

#### Days 1-2: Foundation

- ✅ CLI skeleton with Typer integration
- ✅ Hydra configuration management setup
- ✅ Basic command structure and help system
- ✅ **Production**: Polars + Pandas fallback data loader
- ✅ **Production**: Result directory with audit trail (config + git hash)

#### Days 3-4: Engine Development

- ✅ Replay engine extraction from test fixtures
- ✅ Streaming data loader implementation
- ✅ Event-driven metrics collection framework
- ✅ **Production**: Real-time latency profiling with `perf_counter_ns()`
- ✅ **Production**: Streaming CSV metrics writer for memory efficiency

#### Days 5-7: Integration & Testing

- ✅ End-to-end single backtest workflow
- ✅ Performance optimization and validation
- ✅ Result serialization and reporting
- ✅ Walk-forward analysis implementation
- ✅ **Production**: Determinism test with SHA-256 verification
- ✅ **Production**: Configurable risk-free rate for Sharpe calculation

### Week 2: Advanced Features (Stretch Goals)

- Hydra multirun optimization
- Parallel execution with joblib/ray
- Matplotlib visualization components
- Jupyter notebook integration helpers
- Cross-platform determinism validation
- Matplotlib visualization components
- Jupyter notebook integration helpers

---

## Configuration Examples

### Basic Backtest Configuration

```yaml
# configs/eurusd_basic.yaml
strategy:
  symbol: "EURUSD"
  timeframes: ["1m", "1h", "4h"]

risk:
  model: "atr"
  risk_per_trade: 0.01
  atr_period: 14
  sl_atr_multiple: 1.5
  tp_rr: 2.0

account:
  initial_balance: 10000.0
  commission_per_trade: 0.0

data:
  path: "data/EURUSD_2024_1m.parquet"
  date_column: "timestamp"
  ohlcv_columns: ["open", "high", "low", "close", "volume"]
```

### Parameter Sweep Configuration

```yaml
# configs/sweep/risk_optimization.yaml
defaults:
  - base_strategy
  - _self_

hydra:
  mode: MULTIRUN
  sweeper:
    _target_: hydra._internal.BasicSweeper
    max_jobs: 4

risk:
  risk_per_trade: 0.005,0.01,0.015,0.02
  sl_atr_multiple: 1.0,1.5,2.0
  tp_rr: 1.5,2.0,2.5,3.0
```

---

## Success Factors

### Key Enablers

1. **Strong Foundation**: 90% code reuse from Phase 7 components
2. **Clear Architecture**: Event-driven design with clean separation
3. **Performance Focus**: Streaming processing and Polars optimization
4. **Configuration-Driven**: Hydra's powerful parameter management
5. **Incremental Approach**: Build and test one component at a time
6. **Production-Quality**: Real latency profiling, memory efficiency, audit trails

### Critical Dependencies

- Phase 7 components must remain stable during development
- Test fixtures provide reliable patterns for replay engine
- Polars performance characteristics meet 10-second target
- Hydra multirun capabilities scale to parameter sweep requirements
- Graceful degradation for dependency management (Polars → Pandas fallback)

---

## Production-Quality Summary

The updated Phase 8 plan incorporates **enterprise-grade improvements**:

### 🔧 **Robustness Enhancements**

- **Dependency Resilience**: Polars + Pandas fallback for broader adoption
- **Memory Efficiency**: Streaming CSV writes prevent memory bloat on large datasets
- **Cross-Platform**: Deterministic results across Linux/macOS/Windows

### 📊 **Performance & Monitoring**

- **Real Latency Data**: `perf_counter_ns()` profiling at each pipeline stage
- **Hot Spot Identification**: Actual performance bottleneck detection
- **Configurable Metrics**: Risk-free rate and sampling frequency parameters

### 🔍 **Audit & Reproducibility**

- **Complete Provenance**: Config copy + git commit hash in results
- **SHA-256 Determinism**: Automated verification of identical runs
- **Research Trail**: Full reproducibility for scientific validation

---

## Conclusion

Phase 8 represents a **high-confidence, production-ready implementation** with strong foundation reuse and enterprise-quality features. The existing Phase 7 infrastructure provides 90% of the needed components, while the production enhancements ensure robust, scalable operation.

**Recommendation**: Proceed with implementation incorporating all production-quality recommendations for immediate enterprise deployment readiness.

**Next Steps**:

1. Begin CLI skeleton development with Typer + Hydra
2. Extract replay patterns from existing test fixtures
3. Implement streaming metrics collection framework
4. Validate performance against 10-second target

---

_For technical questions or implementation details, refer to the Phase 8 Jupyter notebook analysis or contact the development team._
