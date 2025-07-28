"""
Main CLI application for quantitative backtesting.

This module implements the command-line interface using Typer for command management.
Supports single backtests, walk-forward analysis, and parameter optimization sweeps.
"""

from __future__ import annotations

import hashlib
import json
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
    import yaml

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file) as f:
        config_dict = yaml.safe_load(f)

    return config_dict if config_dict is not None else {}


def execute_backtest(
    cfg: dict[str, Any], walk: int | None = None, train_fraction: float = 0.5
) -> None:
    """Execute backtest with given configuration."""
    # Create result directory
    result_dir = Path("results") / f"backtest_{time.strftime('%Y%m%d_%H%M%S')}"
    result_dir.mkdir(parents=True, exist_ok=True)

    # Execute backtest
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
                typer.echo("❌ Walk-forward analysis failed")
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
                typer.echo(f"✅ Walk-forward analysis completed: {len(results)} folds")
            else:
                # Single backtest
                typer.echo("Running single backtest...")
                result = runner.run()

            # Extract metrics from result
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

                        from quant_algo.visual.plot_builder import (
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

                        run_ctx = RunContext(
                            str(result.result_dir if result.result_dir else result_dir),
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
                            generate_equity_curve_plot([result], result_dir)

                    except ImportError:
                        # Fallback to basic equity curve
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
) -> None:
    """Run parameter optimization sweep.

    Examples:
        # Basic parameter sweep
        quantbt multirun --sweep configs/sweeps/risk_optimization.yaml

        # Parallel execution
        quantbt multirun --sweep configs/sweeps/risk_optimization.yaml --jobs 8
    """
    import time

    import yaml

    from services.sweep import ParameterSweepEngine, SweepConfiguration, SweepParameter

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

    # Parse sweep parameters
    try:
        parameters = []
        param_count = 1

        for param_name, param_config in sweep_dict.items():
            if isinstance(param_config, list):
                # Simple list of values
                param_values = param_config
            elif isinstance(param_config, dict) and "values" in param_config:
                # Extended configuration with metadata
                param_values = param_config["values"]
            else:
                typer.echo(f"❌ Invalid parameter config for '{param_name}'", err=True)
                raise typer.Exit(1)

            parameters.append(SweepParameter(name=param_name, values=param_values))
            param_count *= len(param_values)

        typer.echo(
            f"📊 Sweep parameters: {len(parameters)} params, {param_count} combinations"
        )

        if param_count > 100:
            typer.echo(
                f"⚠️  Large sweep with {param_count} combinations. This may take significant time."
            )

    except Exception as e:
        typer.echo(f"❌ Failed to parse sweep parameters: {e}", err=True)
        raise typer.Exit(1) from e

    # Create sweep configuration
    sweep_cfg = SweepConfiguration(
        base_config=base_cfg, parameters=parameters, max_workers=jobs, output_dir=output
    )

    # Execute sweep
    try:
        typer.echo(f"🚀 Starting parameter sweep with {jobs} workers...")
        start_time = time.time()

        engine = ParameterSweepEngine(sweep_cfg)
        results = engine.run_sweep()

        # Save results
        results_path = engine.save_results()

        # Summary
        end_time = time.time()
        successful = sum(1 for r in results if r.success)

        typer.echo("\n🎯 Sweep Summary:")
        typer.echo(f"   • Total combinations: {len(results)}")
        typer.echo(f"   • Successful runs: {successful}")
        typer.echo(f"   • Failed runs: {len(results) - successful}")
        typer.echo(f"   • Total time: {end_time - start_time:.1f} seconds")
        typer.echo(f"   • Results saved to: {results_path}")

        if successful > 0:
            # Show top results
            top_results = engine.get_top_results(5)
            typer.echo("\n🏆 Top 5 Results:")
            for i, result in enumerate(top_results, 1):
                typer.echo(
                    f"   {i}. Sharpe: {result.sharpe_ratio:.3f}, "
                    f"Return: {result.total_return:.2%}, "
                    f"Params: {result.parameter_combination}"
                )

            # Parameter importance analysis
            importance = engine.analyze_parameter_importance()
            if importance:
                typer.echo("\n📈 Parameter Importance:")
                sorted_importance = sorted(
                    importance.items(), key=lambda x: x[1], reverse=True
                )
                for param_name, score in sorted_importance:
                    typer.echo(f"   • {param_name}: {score:.3f}")

        typer.echo("\n✅ Parameter sweep completed successfully!")

    except Exception as e:
        typer.echo(f"❌ Parameter sweep failed: {e}", err=True)
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
