"""
Main CLI application for quantitative backtesting.

This module implements the command-line interface using Typer for command management.
Supports single backtests, walk-forward analysis, and parameter optimization sweeps.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import typer
from omegaconf import DictConfig, OmegaConf

# Live trading imports
from infra.brokers import AlpacaBroker, BinanceFuturesBroker
from infra.brokers.alpaca import AlpacaConfig
from infra.brokers.binance_futures import BinanceConfig

from ..models import BacktestConfig, BacktestResult
from ..runner import BacktestRunner


def generate_equity_curve_plot(
    results: BacktestResult | list[BacktestResult], output_path: Path
) -> None:
    """Generate equity curve plot from backtest result(s).

    Args:
        results: Single backtest result or list of results (for walk-forward)
        output_path: Path to save the plot
    """
    try:
        from datetime import datetime

        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError as err:
        raise ImportError(
            "matplotlib required for plotting. Install with: pip install matplotlib"
        ) from err

    # Handle both single result and list of results
    if isinstance(results, list):
        # Walk-forward analysis - plot aggregate metrics
        if not results or not any(hasattr(r, "metrics") and r.metrics for r in results):
            raise ValueError("No trade data available for plotting")

        # Aggregate metrics across all folds
        total_pnl = sum(r.metrics.get("total_pnl", 0) for r in results if r.metrics)
        total_trades = sum(
            r.metrics.get("total_trades", 0) for r in results if r.metrics
        )
        winning_trades = sum(
            r.metrics.get("winning_trades", 0) for r in results if r.metrics
        )
        total_fees = sum(r.metrics.get("total_fees", 0) for r in results if r.metrics)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Create plot for walk-forward results
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # Plot 1: Aggregate metrics
        metrics = ["Total PnL", "Total Fees"]
        values = [total_pnl, total_fees]

        ax1.bar(metrics, values, color=["green" if v > 0 else "red" for v in values])
        ax1.set_title(f"Walk-Forward Analysis Results ({len(results)} folds)")
        ax1.set_ylabel("USD")
        ax1.grid(True, alpha=0.3)

        # Plot 2: Trading stats
        stats = ["Total Trades", "Winning Trades", "Win Rate %"]
        stat_values = [total_trades, winning_trades, win_rate]

        ax2.bar(stats, stat_values, color=["blue", "green", "orange"])
        ax2.set_title("Aggregate Trading Statistics")
        ax2.grid(True, alpha=0.3)

    else:
        # Single backtest result
        result = results
        if not hasattr(result, "metrics") or not result.metrics:
            raise ValueError("No trade data available for plotting")

        # Create plot for single result
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # Plot 1: Basic metrics as bar chart
        metrics = ["Total PnL", "Total Fees", "Max Drawdown"]
        values = [
            result.metrics.get("total_pnl", 0),
            result.metrics.get("total_fees", 0),
            result.metrics.get("max_drawdown", 0),
        ]

        ax1.bar(metrics, values, color=["green" if v > 0 else "red" for v in values])
        ax1.set_title("Backtest Performance Metrics")
        ax1.set_ylabel("USD")
        ax1.grid(True, alpha=0.3)

        # Plot 2: Strategy stats
        stats = ["Total Trades", "Winning Trades", "Win Rate %"]
        stat_values = [
            result.metrics.get("total_trades", 0),
            result.metrics.get("winning_trades", 0),
            result.metrics.get("win_rate", 0) * 100,
        ]

        ax2.bar(stats, stat_values, color=["blue", "green", "orange"])
        ax2.set_title("Trading Statistics")
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


async def _run_live_trading(broker_name: str, cfg: DictConfig, verbose: bool) -> None:
    """Execute live trading with specified broker.

    Args:
        broker_name: Either 'binance' or 'alpaca'
        cfg: Configuration object
        verbose: Enable verbose output
    """
    import os

    from infra.brokers.alpaca import AlpacaBroker
    from infra.brokers.binance_futures import BinanceFuturesBroker

    broker: BinanceFuturesBroker | AlpacaBroker

    if broker_name == "binance":
        # Validate Binance API credentials
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")

        if not api_key or not api_secret:
            typer.echo(
                "❌ Missing Binance API credentials. Set BINANCE_API_KEY and BINANCE_API_SECRET",
                err=True,
            )
            raise typer.Exit(1)

        config = BinanceConfig(
            binance_api_key=api_key,
            binance_api_secret=api_secret,
            binance_testnet=True,  # Always use testnet for safety
        )

        broker = BinanceFuturesBroker(config)
        typer.echo("✅ Binance Futures testnet broker initialized")

    elif broker_name == "alpaca":
        # Validate Alpaca API credentials
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")

        if not api_key or not api_secret:
            typer.echo(
                "❌ Missing Alpaca API credentials. Set ALPACA_API_KEY and ALPACA_API_SECRET",
                err=True,
            )
            raise typer.Exit(1)

        alpaca_config = AlpacaConfig(
            alpaca_key_id=api_key,
            alpaca_secret=api_secret,
            alpaca_paper=True,  # Always use paper trading for safety
        )

        broker = AlpacaBroker(alpaca_config)
        typer.echo("✅ Alpaca paper trading broker initialized")
    else:
        typer.echo(f"❌ Unsupported broker: {broker_name}", err=True)
        raise typer.Exit(1)

    # Test broker connection
    typer.echo("🔍 Testing broker connection...")
    account_info = await broker.account()

    if verbose:
        typer.echo(f"Account balance: ${account_info.cash_balance:.2f}")
        typer.echo(f"Account equity: ${account_info.equity:.2f}")

    # For now, just test the connection
    typer.echo("✅ Live trading connection test successful")

    # Clean up
    await broker.close()


# Initialize Typer app
app = typer.Typer(
    name="quantbt",
    help="Quantitative Algorithm Backtesting Platform",
    add_completion=False,
)


def load_configuration(config_path: str) -> dict[str, Any]:
    """Load configuration from YAML file with error handling.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary

    Raises:
        Exception: If configuration cannot be loaded
    """
    import logging

    import yaml

    logger = logging.getLogger(__name__)

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file) as f:
        config_dict = yaml.safe_load(f)

    if config_dict is None:
        return {}

    # Ensure config_dict is a dictionary
    if not isinstance(config_dict, dict):
        raise ValueError(
            f"Configuration file must contain a dictionary, got {type(config_dict)}"
        )

    # Configuration validation and warnings
    _validate_config(config_dict, logger)

    return config_dict


def _validate_config(config: dict[str, Any], logger: logging.Logger) -> None:
    """Validate configuration and emit warnings for potential issues."""

    # Check volume filter setting
    candidate_config = config.get("candidate", {})
    filters_config = candidate_config.get("filters", {})
    volume_multiple = filters_config.get("volume_multiple", 1.2)

    if volume_multiple == 0:
        logger.warning(
            "Volume filter disabled (volume_multiple=0). This is recommended for data with poor volume quality."
        )

    # Check aggregation vs data timeframe consistency
    data_config = config.get("data", {})
    data_timeframe = data_config.get("timeframe", "5m")

    agg_config = config.get("aggregation", {})
    source_tf_minutes = agg_config.get("source_tf_minutes", 5)

    # Convert data timeframe to minutes for comparison
    data_tf_minutes = _timeframe_to_minutes(data_timeframe)

    if data_tf_minutes != source_tf_minutes:
        logger.warning(
            f"Data timeframe ({data_timeframe} = {data_tf_minutes}min) doesn't match "
            f"aggregation source_tf_minutes ({source_tf_minutes}min). "
            f"This may cause aggregation issues."
        )

    # Check for event dumping configuration
    execution_config = config.get("execution", {})
    dump_events = execution_config.get("dump_events", False)

    if dump_events:
        logger.info(
            "Event dumping enabled - parquet files will be created for visualization"
        )


def _timeframe_to_minutes(timeframe: str) -> int:
    """Convert timeframe string to minutes."""
    if timeframe.endswith("m"):
        return int(timeframe[:-1])
    elif timeframe.endswith("h") or timeframe.endswith("H"):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith("d") or timeframe.endswith("D"):
        return int(timeframe[:-1]) * 1440
    else:
        return 5  # Default fallback


def execute_backtest(
    cfg: dict[str, Any], walk: int | None = None, train_fraction: float = 0.5
) -> None:
    """Execute backtest with given configuration."""
    # Create result directory
    result_dir = Path("results") / f"backtest_{time.strftime('%Y%m%d_%H%M%S')}"
    result_dir.mkdir(parents=True, exist_ok=True)

    # Execute backtest
    result = None  # Initialize to prevent NameError
    results = None  # Initialize to prevent NameError

    try:
        # Create BacktestConfig with defaults for missing sections
        config_dict = cfg.copy()

        # Ensure all required sections exist with defaults
        if "execution" not in config_dict:
            config_dict["execution"] = {}
        if "walk_forward" not in config_dict:
            config_dict["walk_forward"] = {}
        if "sweep" not in config_dict:
            config_dict["sweep"] = {}

        backtest_cfg = BacktestConfig(**config_dict)
        runner = BacktestRunner(backtest_cfg)

        if walk:
            # Walk-forward analysis
            typer.echo(f"Running walk-forward analysis with {walk} folds...")
            results = runner.run_walk_forward()

            if results and results[0].success:
                typer.echo(f"✅ Walk-forward analysis completed: {len(results)} folds")

                # Save individual fold results
                for result in results:
                    fold_file = result_dir / f"fold_{result.fold_id}_result.json"
                    save_result_json(result, fold_file)

                # Calculate and save aggregate statistics
                save_walk_forward_summary(
                    results, result_dir / "walk_forward_summary.json"
                )

            else:
                error_msg = results[0].error_message if results else "Unknown error"
                typer.echo(f"❌ Walk-forward analysis failed: {error_msg}")
                raise typer.Exit(1)
        else:
            # Single backtest
            typer.echo("Running single backtest...")
            result = runner.run()

            if result.success:
                typer.echo("✅ Backtest completed successfully")
                save_result_json(result, result_dir / "result.json")
            else:
                typer.echo(f"❌ Backtest failed: {result.error_message}")
                raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"❌ Backtest failed: {e}", err=True)
        raise typer.Exit(1) from e


def create_result_directory(base_path: Path, config: DictConfig) -> Path:
    """Create timestamped result directory with audit trail.

    Args:
        base_path: Base directory for results
        config: Hydra configuration

    Returns:
        Path to created result directory
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    result_dir = base_path / f"backtest_{timestamp}"
    result_dir.mkdir(parents=True, exist_ok=True)

    # Save configuration copy
    config_file = result_dir / "config.yaml"
    OmegaConf.save(config, config_file)

    # Record git commit hash and environment info
    provenance = {
        "timestamp": timestamp,
        "python_version": sys.version,
        "config_hash": hashlib.sha256(str(config).encode()).hexdigest(),
    }

    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        provenance["git_commit"] = git_hash
    except (subprocess.CalledProcessError, FileNotFoundError):
        typer.echo("Warning: Could not retrieve git commit hash", err=True)
        provenance["git_commit"] = "unknown"

    with open(result_dir / "provenance.json", "w") as f:
        json.dump(provenance, f, indent=2)

    return result_dir


def save_result_json(result: BacktestResult, filepath: Path) -> None:
    """Save backtest result to JSON file.

    Args:
        result: BacktestResult to save
        filepath: Output file path
    """
    import json

    with open(filepath, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)


def save_walk_forward_summary(results: list[BacktestResult], filepath: Path) -> None:
    """Save walk-forward analysis summary.

    Args:
        results: List of fold results
        filepath: Output file path
    """
    import json

    successful_results = [r for r in results if r.success]

    if not successful_results:
        summary = {
            "total_folds": len(results),
            "successful_folds": 0,
            "success_rate": 0.0,
            "error": "All folds failed",
        }
    else:
        # Calculate aggregate metrics
        metrics_keys = successful_results[0].metrics.keys()
        aggregate_metrics = {}

        for key in metrics_keys:
            values = [
                r.metrics.get(key, 0)
                for r in successful_results
                if isinstance(r.metrics.get(key), int | float)
            ]
            if values:
                aggregate_metrics[f"avg_{key}"] = sum(values) / len(values)
                aggregate_metrics[f"std_{key}"] = (
                    sum((v - aggregate_metrics[f"avg_{key}"]) ** 2 for v in values)
                    / len(values)
                ) ** 0.5

        summary = {
            "total_folds": len(results),
            "successful_folds": len(successful_results),
            "success_rate": len(successful_results) / len(results),
            "aggregate_metrics": aggregate_metrics,
            "fold_results": [r.to_dict() for r in results],
        }

    with open(filepath, "w") as f:
        json.dump(summary, f, indent=2, default=str)


@app.command()
def run(
    data: str = typer.Argument(
        None, help="Path to historical data file (optional for live trading)"
    ),
    config: str = typer.Option(
        "configs/base.yaml", "--config", "-c", help="Configuration file"
    ),
    output: str = typer.Option("results", "--output", "-o", help="Output directory"),
    walk: int | None = typer.Option(
        None, "--walk", help="Number of walk-forward folds"
    ),
    train_fraction: float = typer.Option(
        0.5, "--train-fraction", help="Training fraction for walk-forward"
    ),
    plot: bool = typer.Option(False, "--plot", help="Generate equity curve plot"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    live: str | None = typer.Option(
        None, "--live", "-l", help="Enable live trading: 'binance' or 'alpaca'"
    ),
) -> None:
    """Execute backtest with specified configuration.

    Examples:
        # Single backtest
        quantbt run --data data/EURUSD_1m.parquet --config configs/eurusd.yaml

        # Walk-forward analysis
        quantbt run --data data/BTC_1m.csv --walk 6 --config configs/btc.yaml

        # Live trading with Binance testnet
        quantbt run --config configs/btc.yaml --live binance

        # Live trading with Alpaca paper
        quantbt run --config configs/stocks.yaml --live alpaca
    """

    # Validate inputs
    config_path = Path(config)

    # Live trading mode validation
    if live:
        if live not in ["binance", "alpaca"]:
            typer.echo(
                f"Error: Invalid live broker '{live}'. Use 'binance' or 'alpaca'",
                err=True,
            )
            raise typer.Exit(1)

        # For live trading, data path is optional
        if data and not Path(data).exists():
            typer.echo(
                f"⚠️ Data file not found: {data}. Live mode will use broker feeds.",
                err=True,
            )
        data_path = Path(data) if data else None
    else:
        # For backtesting, data path is required
        if not data:
            typer.echo("Error: Data file required for backtesting mode", err=True)
            raise typer.Exit(1)
        data_path = Path(data)
        if not data_path.exists():
            typer.echo(f"Error: Data file not found: {data_path}", err=True)
            raise typer.Exit(1)

    if not config_path.exists():
        typer.echo(f"Error: Config file not found: {config_path}", err=True)
        raise typer.Exit(1)

    # Initialize Hydra configuration
    try:
        # Simple YAML loading for now
        import yaml

        with open(config_path) as f:
            cfg_dict = yaml.safe_load(f)

        # Convert to OmegaConf for compatibility
        from omegaconf import OmegaConf

        cfg = OmegaConf.create(cfg_dict)
    except Exception as e:
        typer.echo(f"Error loading configuration: {e}", err=True)
        raise typer.Exit(1) from e

    # Update config with walk-forward settings if specified
    if walk:
        # Ensure walk_forward section exists
        if "walk_forward" not in cfg:
            cfg["walk_forward"] = {}
        cfg["walk_forward"]["folds"] = walk
        cfg["walk_forward"]["train_fraction"] = train_fraction

    # Set data path from command line argument (if provided)
    if data_path:
        cfg["data"]["path"] = str(data_path)

    # Configure live trading if requested
    if live:
        # Ensure execution section exists
        if "execution" not in cfg:
            cfg["execution"] = {}
        cfg["execution"]["mode"] = "live"
        cfg["execution"]["live"] = {"broker": live}

        # Disable walk-forward for live trading
        if walk:
            typer.echo(
                "⚠️ Walk-forward analysis disabled in live trading mode", err=True
            )
            walk = None

        typer.echo(f"🚀 Live trading mode enabled with {live.upper()} broker")
    else:
        # Ensure we're in backtest mode
        if "execution" not in cfg:
            cfg["execution"] = {}
        cfg["execution"]["mode"] = "backtest"

    # Create result directory with audit trail
    output_path = Path(output)
    result_dir = create_result_directory(output_path, cfg)

    if verbose:
        typer.echo("Starting backtest...")
        typer.echo(f"Data: {data_path}")
        typer.echo(f"Config: {config_path}")
        typer.echo(f"Output: {result_dir}")
        if walk:
            typer.echo(f"Walk-forward folds: {walk}")

    # Execute based on mode
    try:
        if live:
            # Live trading execution
            import asyncio

            asyncio.run(_run_live_trading(live, cfg, verbose))
        else:
            # Convert OmegaConf to BacktestConfig
            config_container = OmegaConf.to_container(cfg, resolve=True)
            if not isinstance(config_container, dict):
                raise ValueError("Configuration must be a dictionary")

            # Use cast to tell mypy this is the right type
            from typing import cast

            typed_config_dict = cast(dict[str, Any], config_container)

            backtest_config = BacktestConfig(**typed_config_dict)

            runner = BacktestRunner(backtest_config)

            if walk:
                # Walk-forward analysis
                typer.echo(f"Running walk-forward analysis with {walk} folds...")
                results = runner.run_walk_forward()

                # Extract and display walk-forward metrics
                successful_results = [r for r in results if r.success]
                if successful_results:
                    total_trades_all_folds = sum(
                        r.metrics.get("total_trades", 0) for r in successful_results
                    )
                    total_pnl_all_folds = sum(
                        r.metrics.get("total_pnl", 0) for r in successful_results
                    )
                    avg_sharpe = sum(
                        r.metrics.get("sharpe_ratio", 0) for r in successful_results
                    ) / len(successful_results)
                    avg_win_rate = sum(
                        r.metrics.get("win_rate", 0) for r in successful_results
                    ) / len(successful_results)

                    typer.echo(
                        f"✅ Walk-forward analysis completed: {len(results)} folds"
                    )
                    typer.echo(
                        f"📊 Total trades: {total_trades_all_folds}, Total P&L: ${total_pnl_all_folds:.2f}"
                    )
                    typer.echo(
                        f"📈 Average Sharpe: {avg_sharpe:.3f}, Average Win Rate: {avg_win_rate:.2%}"
                    )
                else:
                    typer.echo(
                        f"❌ Walk-forward analysis completed: {len(results)} folds (all failed)"
                    )

            else:
                # Single backtest
                typer.echo("Running single backtest...")
                result = runner.run()

                # Extract metrics from single backtest result
                if hasattr(result, "metrics") and isinstance(result.metrics, dict):
                    trade_metrics = result.metrics.get("trade_metrics", {})
                    total_trades = trade_metrics.get("total_trades", 0)
                    total_pnl = trade_metrics.get("total_pnl", 0.0)
                else:
                    # Fallback for object-style metrics
                    total_trades = (
                        getattr(result.metrics, "total_trades", 0)
                        if hasattr(result, "metrics")
                        else 0
                    )
                    total_pnl = (
                        getattr(result.metrics, "total_pnl", 0.0)
                        if hasattr(result, "metrics")
                        else 0.0
                    )

                typer.echo(
                    f"✅ Backtest completed: {total_trades} trades, P&L: ${total_pnl:.2f}"
                )

        # Generate equity curve plot if requested
        if plot:
            try:
                if walk:
                    typer.echo(
                        "Generating equity curve plot for walk-forward analysis..."
                    )
                    generate_equity_curve_plot(results, result_dir)
                else:
                    typer.echo("Generating equity curve plot...")

                    # Enhanced visualization with candlestick + overlays
                    try:
                        import os

                        from scripts.visualization.plot_builder import (
                            build_plotly,
                            display_chart_in_chatgpt,
                        )

                        # Create run context for visualization
                        class RunContext:
                            def __init__(
                                self, out_dir: str, symbol: str = "BTCUSD"
                            ) -> None:
                                self.out_dir = Path(out_dir)
                                self.data_path = self.out_dir / "data.csv"
                                self.trades_path = self.out_dir / "trades.csv"
                                self.events_path = self.out_dir / "events.parquet"
                                self.symbol = symbol

                        # Use result_dir for single backtest visualization
                        run_ctx = RunContext(
                            str(result_dir),
                            cfg.get("data", {}).get("symbol", "BTCUSD"),
                        )

                        # Generate Plotly chart
                        if run_ctx.data_path.exists():
                            fig = build_plotly(run_ctx)

                            # Display in ChatGPT or save to file
                            if os.getenv("CHATGPT_ENV") == "1":
                                display_chart_in_chatgpt(fig)
                                typer.echo("📊 Interactive chart displayed in ChatGPT")
                            else:
                                chart_path = result_dir / "interactive_chart.html"
                                fig.write_html(str(chart_path))
                                typer.echo(
                                    f"📊 Interactive chart saved to {chart_path}"
                                )
                        else:
                            # Fallback to equity curve
                            if result:
                                generate_equity_curve_plot([result], result_dir)

                    except ImportError:
                        # Fallback to basic equity curve
                        if result:
                            generate_equity_curve_plot([result], result_dir)

                typer.echo(f"📊 Charts saved to {result_dir}/")
            except Exception as e:
                typer.echo(f"⚠️ Plot generation failed: {e}", err=True)

    except Exception as e:
        typer.echo(f"❌ Backtest failed: {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def multirun(
    config: str = typer.Option(
        "configs/base.yaml", "--config", "-c", help="Base configuration file"
    ),
    sweep: str = typer.Option(
        ..., "--sweep", "-s", help="Parameter sweep configuration"
    ),
    output: str = typer.Option(
        "sweeps", "--output", "-o", help="Output directory for sweep results"
    ),
    jobs: int = typer.Option(4, "--jobs", "-j", help="Number of parallel jobs"),
    method: str = typer.Option(
        "grid", "--method", "-m", help="Search method: 'grid', 'bayesian', 'random'"
    ),
    trials: int = typer.Option(
        None, "--trials", "-t", help="Number of trials (overrides grid enumeration)"
    ),
    timeout: int = typer.Option(None, "--timeout", help="Timeout in seconds"),
    multifidelity: bool = typer.Option(
        False, "--multifidelity", help="Enable multi-fidelity optimization"
    ),
    cache: bool = typer.Option(
        True, "--cache/--no-cache", help="Enable preprocessing cache"
    ),
) -> None:
    """Run parameter optimization sweep with advanced search strategies.

    Examples:
        # Traditional grid search
        quantbt multirun --sweep configs/sweeps/risk_optimization.yaml

        # Bayesian optimization (requires optuna)
        quantbt multirun --sweep configs/sweeps/params.yaml --method bayesian --trials 200

        # Parallel random search
        quantbt multirun --sweep configs/sweeps/params.yaml --method random --trials 100 --jobs 8

        # Multi-fidelity optimization
        quantbt multirun --sweep configs/sweeps/params.yaml --method bayesian --multifidelity
    """
    import time

    import yaml

    # Load base configuration
    try:
        cfg_dict = load_configuration(config)
        base_cfg = BacktestConfig(**cfg_dict)
        typer.echo(f"✅ Loaded base config: {config}")
    except Exception as e:
        typer.echo(f"❌ Failed to load base config: {e}", err=True)
        raise typer.Exit(1) from e

    # Load sweep configuration
    sweep_path = Path(sweep)
    if not sweep_path.exists():
        typer.echo(f"❌ Sweep config not found: {sweep_path}", err=True)
        raise typer.Exit(1)

    try:
        with open(sweep_path) as f:
            sweep_dict = yaml.safe_load(f)
        typer.echo(f"✅ Loaded sweep config: {sweep}")
    except Exception as e:
        typer.echo(f"❌ Failed to load sweep config: {e}", err=True)
        raise typer.Exit(1) from e

    # Determine optimization method and configuration
    # Validate required parameters for advanced methods
    needs_trials = method in ["bayesian", "random"]
    if needs_trials and trials is None:
        typer.echo(f"❌ {method} search requires --trials parameter", err=True)
        raise typer.Exit(1)

    # Continue with valid configuration
    if method == "grid":
        # Traditional grid search using existing sweep engine
        typer.echo("🔧 Using traditional grid search...")
        from services.sweep import (
            ParameterSweepEngine,
            SweepConfiguration,
            SweepParameter,
        )

        # Parse sweep parameters for grid search
        try:
            parameters = []
            param_count = 1

            for param_name, param_config in sweep_dict.items():
                if isinstance(param_config, list):
                    param_values = param_config
                elif isinstance(param_config, dict) and "values" in param_config:
                    param_values = param_config["values"]
                else:
                    typer.echo(
                        f"❌ Invalid parameter config for '{param_name}'", err=True
                    )
                    raise typer.Exit(1)

                parameters.append(SweepParameter(name=param_name, values=param_values))
                param_count *= len(param_values)

            typer.echo(
                f"📊 Grid search: {len(parameters)} params, {param_count} combinations"
            )

            if param_count > 1000:
                typer.echo(
                    f"⚠️  Large grid with {param_count} combinations. Consider using --method bayesian or --method random"
                )

        except Exception as e:
            typer.echo(f"❌ Failed to parse sweep parameters: {e}", err=True)
            raise typer.Exit(1) from e

        # Create sweep configuration
        sweep_cfg = SweepConfiguration(
            base_config=base_cfg,
            parameters=parameters,
            max_workers=jobs,
            output_dir=output,
        )

        # Execute traditional sweep
        try:
            typer.echo(f"🚀 Starting grid search with {jobs} workers...")
            start_time = time.time()

            sweep_engine = ParameterSweepEngine(sweep_cfg)
            results = sweep_engine.run_sweep()

            # Save results
            results_path = sweep_engine.save_results()

            # Summary
            end_time = time.time()
            successful = sum(1 for r in results if r.success)

            typer.echo("\n🎯 Grid Search Summary:")
            typer.echo(f"   • Total combinations: {len(results)}")
            typer.echo(f"   • Successful runs: {successful}")
            typer.echo(f"   • Failed runs: {len(results) - successful}")
            typer.echo(f"   • Total time: {end_time - start_time:.1f} seconds")
            typer.echo(f"   • Results saved to: {results_path}")

            if successful > 0:
                # Show top results
                top_results = sweep_engine.get_top_results(5)
                typer.echo("\n🏆 Top 5 Results:")
                for i, result in enumerate(top_results, 1):
                    typer.echo(
                        f"   {i}. Sharpe: {result.sharpe_ratio:.3f}, "
                        f"Return: {result.total_return:.2%}, "
                        f"Params: {result.parameter_combination}"
                    )

                # Parameter importance analysis
                importance = sweep_engine.analyze_parameter_importance()
                if importance:
                    typer.echo("\n📈 Parameter Importance:")
                    sorted_importance = sorted(
                        importance.items(), key=lambda x: x[1], reverse=True
                    )
                    for param_name, score in sorted_importance:
                        typer.echo(f"   • {param_name}: {score:.3f}")

            typer.echo("\n✅ Grid search completed successfully!")

        except Exception as e:
            typer.echo(f"❌ Grid search failed: {e}", err=True)
            raise typer.Exit(1) from e

    else:
        # Advanced optimization methods
        try:
            from services.optimization_engine import (
                EnhancedOptimizationEngine,
                OptimizationConfig,
            )
        except ImportError as e:
            typer.echo(f"❌ Enhanced optimization not available: {e}", err=True)
            typer.echo("💡 Install requirements: pip install optuna joblib", err=True)
            raise typer.Exit(1) from e

        typer.echo(f"🧠 Using {method} optimization...")

        # Create optimization configuration
        opt_config = OptimizationConfig(
            method=method,
            n_trials=trials,
            timeout_seconds=timeout,
            n_jobs=jobs,
            use_multifidelity=multifidelity,
            cache_preprocessing=cache,
            output_dir=output,
        )

        # Run enhanced optimization
        try:
            opt_engine = EnhancedOptimizationEngine(base_cfg, opt_config)
            start_time = time.time()

            if method == "bayesian":
                try:
                    import optuna  # type: ignore[import-not-found]

                    typer.echo(
                        f"🔬 Starting Bayesian optimization with {trials} trials..."
                    )
                    study = opt_engine.run_bayesian_optimization()

                    # Extract best parameters
                    best_trial = study.best_trial
                    best_params = best_trial.params
                    best_score = best_trial.value

                    # Map parameter names back to full paths
                    full_params = {}
                    for key, value in best_params.items():
                        # This mapping should match the define_search_space method
                        param_mapping = {
                            "risk_per_trade": "risk.risk_per_trade",
                            "tp_rr": "risk.tp_rr",
                            "sl_atr_multiple": "risk.sl_atr_multiple",
                            "fvg_min_gap_atr": "detectors.fvg.min_gap_atr",
                            "fvg_min_gap_pct": "detectors.fvg.min_gap_pct",
                            "fvg_min_rel_vol": "detectors.fvg.min_rel_vol",
                            "hlz_min_strength": "hlz.min_strength",
                            "hlz_merge_tolerance": "hlz.merge_tolerance",
                            "zone_min_strength": "zone_watcher.min_strength",
                            "pool_strength_threshold": "pools.strength_threshold",
                            "entry_spacing": "candidate.min_entry_spacing_minutes",
                            "ema_tolerance": "candidate.filters.ema_tolerance_pct",
                            "volume_multiple": "candidate.filters.volume_multiple",
                        }
                        full_key = param_mapping.get(key, key)
                        full_params[full_key] = value

                    optimization_result = study

                except ImportError:
                    typer.echo(
                        "❌ Optuna not installed. Install with: pip install optuna",
                        err=True,
                    )
                    raise typer.Exit(1) from None

            elif method == "random":
                typer.echo(f"🎲 Starting random search with {trials} trials...")
                random_results = opt_engine.run_parallel_random_search()

                # Find best result
                successful_results = [r for r in random_results if r["success"]]
                if successful_results:
                    best_result = max(successful_results, key=lambda x: x["score"])
                    full_params = best_result["params"]  # Already in full path format
                    best_score = best_result["score"]
                    optimization_result = random_results
                else:
                    typer.echo("❌ No successful trials in random search", err=True)
                    raise typer.Exit(1)

            # Final validation with full walk-forward
            typer.echo("🔍 Running final validation...")
            try:
                validation_result = opt_engine.validate_best_params(full_params)
                typer.echo("✅ Validation completed successfully")
            except Exception as e:
                typer.echo(f"❌ Validation failed: {e}")
                typer.echo(f"Parameters type: {type(full_params)}")
                typer.echo(f"Parameters content: {full_params}")
                raise typer.Exit(1) from e

            # Generate and save report
            report = opt_engine.generate_report(optimization_result, validation_result)
            report_path = opt_engine.output_dir / "optimization_report.md"
            with open(report_path, "w") as f:
                f.write(report)

            # Summary
            end_time = time.time()
            typer.echo(f"\n🎯 {method.title()} Optimization Summary:")
            typer.echo(f"   • Method: {method}")
            typer.echo(f"   • Trials completed: {trials}")
            typer.echo(f"   • Best score: {best_score:.4f}")
            typer.echo(f"   • Total time: {end_time - start_time:.1f} seconds")
            typer.echo(f"   • Results saved to: {opt_engine.output_dir}")

            typer.echo("\n🏆 Best Parameters:")
            for param, value in full_params.items():
                if isinstance(value, float):
                    typer.echo(f"   • {param}: {value:.6f}")
                else:
                    typer.echo(f"   • {param}: {value}")

            # Validation metrics
            if "validation_metrics" in validation_result:
                validation_metrics = validation_result["validation_metrics"]
                typer.echo("\n📊 Validation Metrics:")
                key_metrics = [
                    "total_pnl_mean",
                    "sharpe_ratio_mean",
                    "win_rate_mean",
                    "total_trades_mean",
                ]
                for key in key_metrics:
                    if key in validation_metrics:
                        typer.echo(f"   • {key}: {validation_metrics[key]:.4f}")

            typer.echo(f"\n📄 Full report: {report_path}")
            typer.echo("\n✅ Advanced optimization completed successfully!")

        except Exception as e:
            typer.echo(f"❌ {method.title()} optimization failed: {e}", err=True)
            raise typer.Exit(1) from e


@app.command()
def validate(
    config: str = typer.Option(
        "configs/base.yaml", "--config", "-c", help="Configuration file to validate"
    ),
) -> None:
    """Validate configuration file."""

    config_path = Path(config)
    if not config_path.exists():
        typer.echo(f"❌ Config file not found: {config_path}", err=True)
        raise typer.Exit(1)

    try:
        # Simple YAML loading for now
        import yaml

        with open(config_path) as f:
            cfg_dict = yaml.safe_load(f)

        # Convert to OmegaConf for compatibility
        from omegaconf import OmegaConf

        cfg = OmegaConf.create(cfg_dict)

        # Convert OmegaConf to BacktestConfig
        backtest_cfg = BacktestConfig(**cfg)

        typer.echo(f"✅ Configuration valid: {config_path}")
        typer.echo(f"Strategy: {backtest_cfg.strategy.symbol}")
        typer.echo(f"Risk model: {backtest_cfg.risk.model}")
        typer.echo(f"Initial balance: ${backtest_cfg.account.initial_balance:.2f}")

    except Exception as e:
        typer.echo(f"❌ Configuration invalid: {e}", err=True)
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
