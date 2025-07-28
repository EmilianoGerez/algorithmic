"""
Data models for backtesting configuration and results.

This module defines Pydantic models for type-safe configuration management
and result serialization. Integrates with Hydra for flexible parameter management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from omegaconf import DictConfig
from pydantic import BaseModel, Field, validator


class WalkForwardConfig(BaseModel):
    """Walk-forward analysis configuration."""

    folds: int = Field(default=6, ge=2, description="Number of walk-forward folds")
    train_fraction: float = Field(
        default=0.5,
        gt=0.1,
        lt=0.9,
        description="Fraction of each fold used for training",
    )


class SweepConfig(BaseModel):
    """Parameter sweep configuration for multirun."""

    enabled: bool = Field(default=False, description="Enable parameter sweeping")
    parameters: dict[str, list[Any]] = Field(
        default_factory=dict, description="Parameters to sweep with their value ranges"
    )
    max_jobs: int = Field(default=4, ge=1, description="Maximum parallel jobs")


class StrategyConfig(BaseModel):
    """Strategy-specific configuration parameters."""

    name: str = Field(description="Strategy name/identifier")
    symbol: str = Field(description="Trading symbol (e.g., EURUSD, BTCUSD)")
    use_mock_strategy: bool = Field(
        default=False, description="Use simple mock strategy instead of full HTF system"
    )
    htf_list: list[str] = Field(
        default=["H4", "D1"],
        description="Higher timeframe list for liquidity detection",
    )
    timeframes: list[str] = Field(
        default=["1m", "1h", "4h"], description="List of timeframes to use"
    )
    min_gap_size: float = Field(
        default=0.001, description="Minimum FVG gap size for detection"
    )

    @validator("timeframes")
    def validate_timeframes(cls, v: list[str]) -> list[str]:
        valid_tfs = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        for tf in v:
            if tf not in valid_tfs:
                raise ValueError(f"Invalid timeframe: {tf}. Valid: {valid_tfs}")
        return v


class RiskConfig(BaseModel):
    """Risk management configuration."""

    model: str = Field(default="atr", description="Risk model (atr, percent)")
    risk_per_trade: float = Field(
        default=0.01,
        ge=0.001,
        le=0.1,
        description="Risk per trade as fraction of account",
    )
    atr_period: int = Field(default=14, ge=1, description="ATR calculation period")
    sl_atr_multiple: float = Field(
        default=1.5, gt=0, description="Stop loss as multiple of ATR"
    )
    tp_rr: float = Field(default=2.0, gt=0, description="Take profit risk/reward ratio")

    # Production enhancement: configurable risk-free rate
    risk_free_rate: float = Field(
        default=0.02,
        ge=0,
        le=0.1,
        description="Annual risk-free rate for Sharpe calculation",
    )
    trading_days_per_year: int = Field(
        default=252, description="Trading days per year for metrics"
    )
    use_population_std: bool = Field(
        default=True,
        description="Use population std dev (ddof=0) for long backtests, sample std dev (ddof=1) for short samples",
    )


class AccountConfig(BaseModel):
    """Account and execution configuration."""

    initial_balance: float = Field(
        default=10000.0, gt=0, description="Starting account balance"
    )
    commission_per_trade: float = Field(
        default=0.0, ge=0, description="Commission per trade"
    )
    max_positions: int = Field(
        default=1, ge=1, description="Maximum concurrent positions"
    )


class DataConfig(BaseModel):
    """Data source configuration."""

    path: str = Field(description="Path to historical data file")
    date_column: str = Field(default="timestamp", description="Date column name")
    start_date: str | None = Field(
        default=None, description="Start date for data filtering"
    )
    end_date: str | None = Field(
        default=None, description="End date for data filtering"
    )
    ohlcv_columns: list[str] = Field(
        default=["open", "high", "low", "close", "volume"],
        description="OHLCV column names",
    )

    @validator("ohlcv_columns")
    def validate_ohlcv(cls, v: list[str]) -> list[str]:
        required = ["open", "high", "low", "close", "volume"]
        if len(v) != 5:
            raise ValueError(f"Must specify exactly 5 OHLCV columns: {required}")
        return v


class ExecutionConfig(BaseModel):
    """Execution environment configuration."""

    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str | None = Field(default=None, description="Log file path")
    enable_latency_profiling: bool = Field(
        default=True, description="Enable latency profiling"
    )
    enable_memory_tracking: bool = Field(
        default=True, description="Enable memory tracking"
    )
    realtime_simulation: bool = Field(
        default=False, description="Simulate real-time execution"
    )
    use_csv_streaming: bool = Field(
        default=False, description="Use direct CSV streaming"
    )
    deterministic_seed: int | None = Field(
        default=42, description="Random seed for deterministic results"
    )
    dump_events: bool = Field(
        default=False, description="Enable events.parquet export for visualization"
    )
    export_data_for_viz: bool = Field(
        default=False, description="Enable data.csv and trades.csv export"
    )


class BacktestConfig(BaseModel):
    """Complete backtesting configuration."""

    class Config:
        extra = "allow"  # Allow extra fields from YAML

    strategy: StrategyConfig = Field(
        default_factory=lambda: StrategyConfig(name="default", symbol="BTCUSDT")
    )
    risk: RiskConfig = Field(default_factory=RiskConfig)
    account: AccountConfig = Field(default_factory=AccountConfig)
    data: DataConfig = Field(default_factory=lambda: DataConfig(path=""))
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    walk_forward: WalkForwardConfig = Field(default_factory=WalkForwardConfig)
    sweep: SweepConfig = Field(default_factory=SweepConfig)

    # HTF liquidity strategy configuration sections (optional)
    pools: dict[str, Any] = Field(default_factory=dict)
    hlz: dict[str, Any] = Field(default_factory=dict)
    zone_watcher: dict[str, Any] = Field(default_factory=dict)
    candidate: dict[str, Any] = Field(default_factory=dict)
    indicators: dict[str, Any] = Field(default_factory=dict)
    aggregation: dict[str, Any] = Field(default_factory=dict)
    fvg: dict[str, Any] = Field(default_factory=dict)
    pivot: dict[str, Any] = Field(default_factory=dict)
    feeds: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_hydra_config(cls, cfg: DictConfig) -> BacktestConfig:
        """Create BacktestConfig from Hydra DictConfig."""
        return cls(
            strategy=StrategyConfig(**cfg.strategy),
            risk=RiskConfig(**cfg.risk),
            account=AccountConfig(**cfg.account),
            data=DataConfig(**cfg.data),
        )


@dataclass
class BacktestMetrics:
    """Comprehensive KPI tracking for backtesting results.

    This class tracks all key performance indicators with production-quality
    enhancements including real latency data and configurable risk metrics.
    """

    # Performance Metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # P&L Metrics
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0

    # Risk Metrics
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # days
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # Timing Metrics
    avg_trade_duration: float = 0.0  # hours
    avg_bars_in_trade: int = 0

    # Production enhancement: Real latency tracking
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    latency_p95_ms: float = 0.0

    # Portfolio Metrics
    starting_equity: float = 10000.0
    ending_equity: float = 0.0
    cagr: float = 0.0

    # Execution Stats
    total_bars_processed: int = 0
    execution_time_seconds: float = 0.0
    bars_per_second: float = 0.0

    def calculate_derived_metrics(
        self, start_time: datetime, end_time: datetime
    ) -> None:
        """Calculate metrics that depend on other values."""
        if self.total_trades > 0:
            self.win_rate = self.winning_trades / self.total_trades

        if self.gross_loss != 0:
            self.profit_factor = abs(self.gross_profit / self.gross_loss)

        self.ending_equity = self.starting_equity + self.total_pnl

        # CAGR calculation
        if self.starting_equity > 0:
            days = (end_time - start_time).days
            if days > 0:
                years = days / 365.25
                self.cagr = (
                    (self.ending_equity / self.starting_equity) ** (1 / years)
                ) - 1

        # Performance metrics
        if self.execution_time_seconds > 0:
            self.bars_per_second = (
                self.total_bars_processed / self.execution_time_seconds
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "avg_trade_duration": self.avg_trade_duration,
            "avg_bars_in_trade": self.avg_bars_in_trade,
            "avg_latency_ms": self.avg_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "starting_equity": self.starting_equity,
            "ending_equity": self.ending_equity,
            "cagr": self.cagr,
            "total_bars_processed": self.total_bars_processed,
            "execution_time_seconds": self.execution_time_seconds,
            "bars_per_second": self.bars_per_second,
        }


@dataclass
class BacktestResult:
    """Complete backtest execution result."""

    config: BacktestConfig
    metrics: Any  # Can be BacktestMetrics or dict
    start_time: datetime
    end_time: datetime
    audit_trail: dict[str, Any]
    success: bool
    error_message: str | None = None
    execution_time_seconds: float = 0.0
    data_start: datetime | None = None
    data_end: datetime | None = None
    result_dir: str | None = None
    fold_id: int | None = None
    total_folds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "config": {
                "strategy": self.config.strategy.dict()
                if hasattr(self.config.strategy, "dict")
                else str(self.config.strategy),
                "risk": self.config.risk.dict()
                if hasattr(self.config.risk, "dict")
                else str(self.config.risk),
                "account": self.config.account.dict()
                if hasattr(self.config.account, "dict")
                else str(self.config.account),
            },
            "metrics": self.metrics.to_dict()
            if hasattr(self.metrics, "to_dict")
            else self.metrics,
            "timestamps": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
            },
            "execution_time_seconds": self.execution_time_seconds,
            "success": self.success,
            "audit_trail": self.audit_trail,
        }

        if self.error_message:
            result["error_message"] = self.error_message
        if self.data_start:
            result["timestamps"]["data_start"] = self.data_start.isoformat()
        if self.data_end:
            result["timestamps"]["data_end"] = self.data_end.isoformat()
        if self.result_dir:
            result["result_dir"] = self.result_dir
        if self.fold_id is not None:
            result["fold_id"] = self.fold_id
        if self.total_folds is not None:
            result["total_folds"] = self.total_folds

        return result


@dataclass
class WalkForwardResult:
    """Walk-forward analysis result containing multiple fold results."""

    config: BacktestConfig
    fold_results: list[BacktestResult]
    aggregate_metrics: BacktestMetrics
    stability_metrics: dict[str, float]

    def calculate_stability_metrics(self) -> None:
        """Calculate robustness metrics across folds."""
        if not self.fold_results:
            return

        # Extract key metrics across folds
        sharpe_ratios = [r.metrics.sharpe_ratio for r in self.fold_results]
        total_pnls = [r.metrics.total_pnl for r in self.fold_results]
        win_rates = [r.metrics.win_rate for r in self.fold_results]

        # Calculate stability statistics using population std dev (ddof=0)
        # This is appropriate for long backtests as suggested in production guidelines
        self.stability_metrics = {
            "sharpe_mean": sum(sharpe_ratios) / len(sharpe_ratios)
            if sharpe_ratios
            else 0,
            "sharpe_std": (
                sum(
                    (x - sum(sharpe_ratios) / len(sharpe_ratios)) ** 2
                    for x in sharpe_ratios
                )
                / len(sharpe_ratios)  # Population std dev (ddof=0)
            )
            ** 0.5
            if len(sharpe_ratios) > 1
            else 0,
            "pnl_mean": sum(total_pnls) / len(total_pnls) if total_pnls else 0,
            "pnl_std": (
                sum((x - sum(total_pnls) / len(total_pnls)) ** 2 for x in total_pnls)
                / len(total_pnls)  # Population std dev (ddof=0)
            )
            ** 0.5
            if len(total_pnls) > 1
            else 0,
            "win_rate_mean": sum(win_rates) / len(win_rates) if win_rates else 0,
            "positive_folds": sum(1 for pnl in total_pnls if pnl > 0),
            "total_folds": len(self.fold_results),
        }
