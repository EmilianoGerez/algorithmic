#!/usr/bin/env python3
"""
Simplified Enhanced QuantBT CLI

A comprehensive terminal interface that organizes all trading tools and services
into an intuitive command structure without requiring additional dependencies.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(
    name="quantbt",
    help="🚀 Quantitative Trading Platform - Enhanced Interface",
    add_completion=False,
)


def show_welcome() -> None:
    """Display welcome message with available commands."""
    welcome = """
🚀 Quantitative Algorithm Trading Platform - Enhanced CLI

📋 AVAILABLE COMMANDS:

📊 DATA MANAGEMENT:
  • data fetch SYMBOL TIMEFRAME    - Fetch market data from Binance
  • data validate FILE             - Validate data quality
  • data info FILE                 - Show data statistics

🎯 BACKTESTING:
  • backtest run                   - Run single backtest
  • backtest walk-forward DATA     - Walk-forward analysis
  • backtest live BROKER           - Live trading (testnet/paper)

🧠 OPTIMIZATION:
  • optimize quick                 - Quick optimization test
  • optimize 3phase                - 3-phase optimization (recommended)
  • optimize bayesian              - Bayesian optimization
  • optimize grid SWEEP_FILE       - Grid search

📊 ANALYSIS:
  • analyze dashboard              - Optimization performance dashboard
  • analyze performance            - Detailed performance analysis
  • analyze backtest RESULT_FILE   - Individual backtest analysis

📈 VISUALIZATION:
  • visualize chart DATA_FILE      - Interactive trading charts
  • visualize equity RESULT_FILE   - Equity curve plots

📡 MONITORING:
  • monitor optimization           - Live optimization tracking
  • monitor system                 - System health check

⚙️ CONFIGURATION:
  • config validate CONFIG_FILE    - Validate configuration
  • config list                    - List available configs
  • config template                - Generate config template

🛠️ TOOLS:
  • tools demo --phase N           - Run demonstration scripts
  • tools debug COMPONENT          - Debug specific components
  • tools cleanup                  - System cleanup

🎯 QUICK START:
  1. quantbt data fetch BTCUSDT 5m --days 7
  2. quantbt backtest run --data data/BTCUSDT_5m_*.csv --plot
  3. quantbt optimize quick --trials 50

Use --help with any command for detailed options.
"""
    print(welcome)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version"),
) -> None:
    """Enhanced Quantitative Trading Platform CLI."""
    if version:
        print("QuantBT Enhanced CLI v2.0.0")
        return

    if ctx.invoked_subcommand is None:
        show_welcome()


# ============================================================================
# DATA COMMANDS
# ============================================================================

data_app = typer.Typer(name="data", help="📊 Data management commands")
app.add_typer(data_app)


@data_app.command("fetch")
def data_fetch(
    symbol: str = typer.Argument(..., help="Symbol (e.g., BTCUSDT, ETHUSDT)"),
    timeframe: str = typer.Argument("5m", help="Timeframe (1m, 5m, 1h, 4h, 1d)"),
    start: str = typer.Option(None, "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(None, "--end", "-e", help="End date (YYYY-MM-DD)"),
    days: int = typer.Option(7, "--days", "-d", help="Days back from today"),
    futures: bool = typer.Option(False, "--futures", "-f", help="Use Binance Futures"),
    output: str = typer.Option("data", "--output", "-o", help="Output directory"),
) -> None:
    """🔽 Fetch historical market data from Binance."""
    print(f"🔽 Fetching {symbol} {timeframe} data...")

    script_path = Path("scripts/fetch_binance_klines.py")
    cmd = ["python", str(script_path), symbol, timeframe]

    if start and end:
        cmd.extend([start, end])
    else:
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        cmd.extend(
            [
                start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            ]
        )

    if futures:
        cmd.append("--futures")
    cmd.extend(["--output", output])

    try:
        subprocess.run(cmd, check=True)
        print("✅ Data fetch completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Data fetch failed: {e}")
        raise typer.Exit(1)


@data_app.command("validate")
def data_validate(
    path: str = typer.Argument(..., help="Path to data file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """✅ Validate market data quality and structure."""
    script_path = Path("scripts/validate_data.py")
    cmd = [sys.executable, str(script_path), path]
    if verbose:
        cmd.append("--verbose")

    try:
        subprocess.run(cmd, check=True)
        print("✅ Data validation completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Data validation failed: {e}")
        raise typer.Exit(1)


@data_app.command("info")
def data_info(path: str = typer.Argument(..., help="Path to data file")) -> None:
    """📈 Show data file information and statistics."""
    try:
        from services.data_loader import DataLoader
        from services.models import BacktestConfig

        config = BacktestConfig()
        loader = DataLoader(config.data)
        info = loader.get_data_info(path)

        print(f"\n📊 Data Information: {Path(path).name}")
        print("-" * 40)
        print(f"Total Rows:  {info['total_rows']:,}")
        print(
            f"Date Range:  {info['date_range']['start']} to {info['date_range']['end']}"
        )
        print(
            f"Price Range: ${info['price_range']['min']:.2f} - ${info['price_range']['max']:.2f}"
        )
        print(f"File Size:   {info['file_size_mb']:.1f} MB")

    except Exception as e:
        print(f"❌ Failed to analyze data: {e}")
        raise typer.Exit(1)


# ============================================================================
# BACKTEST COMMANDS
# ============================================================================

backtest_app = typer.Typer(name="backtest", help="🎯 Backtesting commands")
app.add_typer(backtest_app)


@backtest_app.command("run")
def backtest_run(
    data: str = typer.Option(None, "--data", "-d", help="Path to data file"),
    config: str = typer.Option(
        "configs/base.yaml", "--config", "-c", help="Config file"
    ),
    output: str = typer.Option("results", "--output", "-o", help="Output directory"),
    plot: bool = typer.Option(False, "--plot", "-p", help="Generate charts"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """🚀 Run a single backtest."""
    cmd = ["python", "run_backtest.py", "--config", config]
    if data:
        cmd.extend(["--data", data])
    if plot:
        cmd.append("--plot")
    if verbose:
        cmd.append("--verbose")

    try:
        subprocess.run(cmd, check=True)
        print("✅ Backtest completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Backtest failed: {e}")
        raise typer.Exit(1)


@backtest_app.command("walk-forward")
def backtest_walk_forward(
    data: str = typer.Argument(..., help="Path to data file"),
    config: str = typer.Option(
        "configs/base.yaml", "--config", "-c", help="Config file"
    ),
    folds: int = typer.Option(6, "--folds", "-f", help="Number of folds"),
    train_fraction: float = typer.Option(
        0.5, "--train-fraction", help="Training fraction"
    ),
) -> None:
    """📊 Run walk-forward analysis."""
    cmd = [
        "python",
        "run_backtest.py",
        "--config",
        config,
        "--data",
        data,
        "--walk",
        str(folds),
        "--train-fraction",
        str(train_fraction),
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✅ Walk-forward analysis completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Walk-forward analysis failed: {e}")
        raise typer.Exit(1)


@backtest_app.command("live")
def backtest_live(
    broker: str = typer.Argument(..., help="Broker: binance or alpaca"),
    config: str = typer.Option(
        "configs/base.yaml", "--config", "-c", help="Config file"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """📡 Run live trading (testnet/paper)."""
    cmd = ["python", "run_backtest.py", "--config", config, "--live", broker]
    if verbose:
        cmd.append("--verbose")

    try:
        subprocess.run(cmd, check=True)
        print("✅ Live trading session completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Live trading failed: {e}")
        raise typer.Exit(1)


# ============================================================================
# OPTIMIZATION COMMANDS
# ============================================================================

optimize_app = typer.Typer(name="optimize", help="🧠 Parameter optimization")
app.add_typer(optimize_app)


@optimize_app.command("quick")
def optimize_quick(
    trials: int = typer.Option(50, "--trials", "-n", help="Number of trials"),
    jobs: int = typer.Option(4, "--jobs", "-j", help="Parallel jobs"),
) -> None:
    """⚡ Quick optimization testing."""
    print(f"⚡ Running quick optimization with {trials} trials...")

    cmd = [
        "python",
        "tools/optimization/run_ultra_fast_optimization.py",
        "--trials",
        str(trials),
        "--jobs",
        str(jobs),
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✅ Quick optimization completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Optimization failed: {e}")
        raise typer.Exit(1)


@optimize_app.command("3phase")
def optimize_3phase(
    n1: int = typer.Option(25, "--n1", help="Phase 1 trials (exploration)"),
    n2: int = typer.Option(25, "--n2", help="Phase 2 trials (refinement)"),
    n3: int = typer.Option(50, "--n3", help="Phase 3 trials (validation)"),
    jobs: int = typer.Option(8, "--jobs", "-j", help="Parallel jobs"),
) -> None:
    """🎯 3-phase optimization (exploration → refinement → validation)."""
    print("🎯 Starting 3-phase optimization...")
    print(f"Phase 1: {n1} trials (random exploration)")
    print(f"Phase 2: {n2} trials (focused refinement)")
    print(f"Phase 3: {n3} trials (bayesian validation)")

    cmd = [
        "python",
        "tools/optimization/run_3phase_optimization.py",
        "--n1",
        str(n1),
        "--n2",
        str(n2),
        "--n3",
        str(n3),
        "--jobs",
        str(jobs),
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✅ 3-phase optimization completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Optimization failed: {e}")
        raise typer.Exit(1)


@optimize_app.command("bayesian")
def optimize_bayesian(
    trials: int = typer.Option(200, "--trials", "-n", help="Number of trials"),
    timeout: int = typer.Option(3600, "--timeout", "-t", help="Timeout in seconds"),
    jobs: int = typer.Option(8, "--jobs", "-j", help="Parallel jobs"),
) -> None:
    """🧠 Bayesian optimization with intelligent parameter search."""
    print(f"🧠 Starting Bayesian optimization with {trials} trials...")

    # Create temporary sweep config for bayesian
    import yaml

    sweep_config = {
        "risk_per_trade": {"type": "float", "low": 0.01, "high": 0.05},
        "tp_rr": {"type": "float", "low": 1.5, "high": 3.0},
        "sl_atr_multiple": {"type": "float", "low": 1.0, "high": 3.0},
    }

    sweep_path = Path("temp_bayesian_sweep.yaml")
    with open(sweep_path, "w") as f:
        yaml.dump(sweep_config, f)

    try:
        cmd = [
            "python",
            "-m",
            "services.cli.cli",
            "multirun",
            "--sweep",
            str(sweep_path),
            "--method",
            "bayesian",
            "--trials",
            str(trials),
            "--timeout",
            str(timeout),
            "--jobs",
            str(jobs),
        ]
        subprocess.run(cmd, check=True)
        print("✅ Bayesian optimization completed")
    finally:
        if sweep_path.exists():
            sweep_path.unlink()


@optimize_app.command("grid")
def optimize_grid(
    sweep: str = typer.Argument(..., help="Sweep configuration file"),
    jobs: int = typer.Option(4, "--jobs", "-j", help="Parallel jobs"),
) -> None:
    """🔍 Grid search optimization."""
    print("🔍 Starting grid search optimization...")

    cmd = [
        "python",
        "-m",
        "services.cli.cli",
        "multirun",
        "--sweep",
        sweep,
        "--method",
        "grid",
        "--jobs",
        str(jobs),
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✅ Grid search completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Grid search failed: {e}")
        raise typer.Exit(1)


# ============================================================================
# ANALYSIS COMMANDS
# ============================================================================

analyze_app = typer.Typer(name="analyze", help="📊 Analysis and reporting")
app.add_typer(analyze_app)


@analyze_app.command("dashboard")
def analyze_dashboard(
    results_dir: str = typer.Option(
        "results", "--results", "-r", help="Results directory"
    ),
) -> None:
    """📊 Generate comprehensive optimization dashboard."""
    print("📊 Generating optimization dashboard...")

    cmd = [
        "python",
        "tools/analysis/optimization_dashboard.py",
        "--results-dir",
        results_dir,
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✅ Dashboard generated successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Dashboard generation failed: {e}")
        raise typer.Exit(1)


@analyze_app.command("performance")
def analyze_performance(
    results_dir: str = typer.Option(
        "results", "--results", "-r", help="Results directory"
    ),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Detailed analysis"),
) -> None:
    """📈 Analyze optimization performance metrics."""
    print("📈 Analyzing performance metrics...")

    cmd = [
        "python",
        "tools/analysis/analyze_optimization_performance.py",
        "--results-dir",
        results_dir,
    ]
    if detailed:
        cmd.append("--detailed")

    try:
        subprocess.run(cmd, check=True)
        print("✅ Performance analysis completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Performance analysis failed: {e}")
        raise typer.Exit(1)


@analyze_app.command("backtest")
def analyze_backtest(
    result_path: str = typer.Argument(..., help="Path to backtest result"),
    output: str = typer.Option("analysis", "--output", "-o", help="Output directory"),
) -> None:
    """🔍 Analyze individual backtest results."""
    print(f"🔍 Analyzing backtest: {result_path}")

    cmd = [
        "python",
        "scripts/analysis/analyze_backtest.py",
        result_path,
        "--output",
        output,
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✅ Backtest analysis completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Analysis failed: {e}")
        raise typer.Exit(1)


# ============================================================================
# VISUALIZATION COMMANDS
# ============================================================================

visualize_app = typer.Typer(name="visualize", help="📈 Visualization tools")
app.add_typer(visualize_app)


@visualize_app.command("chart")
def visualize_chart(
    data_path: str = typer.Argument(..., help="Path to data file"),
    trades_path: str = typer.Option(None, "--trades", "-t", help="Path to trades file"),
    output: str = typer.Option("chart.html", "--output", "-o", help="Output file"),
) -> None:
    """📊 Create interactive trading charts."""
    print("📊 Generating trading chart...")

    cmd = [
        "python",
        "scripts/visualization/plot_builder.py",
        data_path,
        "--output",
        output,
    ]
    if trades_path:
        cmd.extend(["--trades", trades_path])

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Chart saved to {output}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Chart generation failed: {e}")
        raise typer.Exit(1)


@visualize_app.command("equity")
def visualize_equity(
    result_path: str = typer.Argument(..., help="Path to backtest result"),
    output: str = typer.Option(
        "equity_curve.png", "--output", "-o", help="Output file"
    ),
) -> None:
    """📈 Generate equity curve plot."""
    print("📈 Generating equity curve...")

    cmd = ["python", "scripts/simple_plot.py", result_path, "--output", output]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Equity curve saved to {output}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Equity curve generation failed: {e}")
        raise typer.Exit(1)


# ============================================================================
# MONITORING COMMANDS
# ============================================================================

monitor_app = typer.Typer(name="monitor", help="📡 Monitoring and tracking")
app.add_typer(monitor_app)


@monitor_app.command("optimization")
def monitor_optimization(
    results_dir: str = typer.Option(
        "results", "--results", "-r", help="Results directory"
    ),
    refresh: int = typer.Option(5, "--refresh", help="Refresh interval (seconds)"),
) -> None:
    """👁️ Monitor live optimization progress."""
    print(f"👁️ Starting optimization monitor (refresh: {refresh}s)...")

    cmd = [
        "python",
        "tools/monitoring/monitor_optimization_live.py",
        "--results-dir",
        results_dir,
        "--refresh",
        str(refresh),
    ]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Monitoring failed: {e}")
        raise typer.Exit(1)


@monitor_app.command("system")
def monitor_system() -> None:
    """⚙️ Show system status and health."""
    print("\n⚙️ System Status Check")
    print("=" * 30)

    # Check Python
    python_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    print(f"Python:     ✅ v{python_version}")

    # Check dependencies
    deps = [
        ("pandas", "Required for data processing"),
        ("polars", "Optional - better performance"),
        ("optuna", "Optional - Bayesian optimization"),
        ("matplotlib", "Optional - plotting"),
        ("typer", "CLI framework"),
    ]

    for dep, desc in deps:
        try:
            module = __import__(dep)
            version = getattr(module, "__version__", "unknown")
            print(f"{dep:10s} ✅ v{version}")
        except ImportError:
            status = "⚠️ Missing" if "Required" in desc else "⚠️ Optional"
            print(f"{dep:10s} {status} - {desc}")

    # Check directories
    dirs = [
        ("data", "Market data files"),
        ("results", "Backtest results"),
        ("configs", "Configuration files"),
        ("cache", "Optimization cache"),
    ]

    print("\nDirectories:")
    for dir_name, desc in dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            files = list(dir_path.glob("*"))
            print(f"{dir_name:10s} ✅ {len(files)} items")
        else:
            print(f"{dir_name:10s} ⚠️ Missing")

    print("\n✅ System check completed")


# ============================================================================
# CONFIG COMMANDS
# ============================================================================

config_app = typer.Typer(name="config", help="⚙️ Configuration management")
app.add_typer(config_app)


@config_app.command("validate")
def config_validate(
    config_path: str = typer.Argument(..., help="Path to config file"),
) -> None:
    """✅ Validate configuration file."""
    cmd = ["python", "-m", "services.cli.cli", "validate", "--config", config_path]

    try:
        subprocess.run(cmd, check=True)
        print("✅ Configuration is valid")
    except subprocess.CalledProcessError as e:
        print(f"❌ Configuration validation failed: {e}")
        raise typer.Exit(1)


@config_app.command("list")
def config_list() -> None:
    """📋 List available configuration files."""
    configs_dir = Path("configs")
    if not configs_dir.exists():
        print("❌ No configs directory found")
        return

    print("\n📋 Available Configurations:")
    print("-" * 30)

    for config_file in configs_dir.glob("*.yaml"):
        stat = config_file.stat()
        size_kb = stat.st_size / 1024
        modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
        print(f"{config_file.name:25s} {size_kb:6.1f}KB  {modified}")


@config_app.command("template")
def config_template(
    strategy: str = typer.Option("htf", "--strategy", help="Strategy type"),
    output: str = typer.Option(
        "custom_config.yaml", "--output", "-o", help="Output file"
    ),
) -> None:
    """📝 Generate configuration template."""
    print(f"📝 Generating {strategy} configuration template...")

    template = {
        "strategy": {"name": strategy, "symbol": "BTCUSDT"},
        "data": {"path": "data/BTCUSDT_5m.csv", "timeframe": "5m"},
        "risk": {"model": "atr", "risk_per_trade": 0.02, "tp_rr": 2.0},
        "account": {"initial_balance": 10000.0, "currency": "USD"},
    }

    import yaml

    with open(output, "w") as f:
        yaml.dump(template, f, default_flow_style=False, indent=2)

    print(f"✅ Template saved to {output}")


# ============================================================================
# TOOLS COMMANDS
# ============================================================================

tools_app = typer.Typer(name="tools", help="🛠️ Utility tools")
app.add_typer(tools_app)


@tools_app.command("demo")
def tools_demo(
    phase: int = typer.Option(1, "--phase", help="Demo phase (1, 2, 3)"),
) -> None:
    """🎮 Run demonstration scripts."""
    print(f"🎮 Running demo phase {phase}...")

    script_path = Path(f"scripts/demos/demo_phase{phase}.py")
    if not script_path.exists():
        print(f"❌ Demo phase {phase} not found")
        raise typer.Exit(1)

    try:
        subprocess.run(["python", str(script_path)], check=True)
        print(f"✅ Demo phase {phase} completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Demo failed: {e}")
        raise typer.Exit(1)


@tools_app.command("debug")
def tools_debug(
    component: str = typer.Argument(..., help="Component to debug"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """🐛 Run debugging tools."""
    print(f"🐛 Running debug tool for {component}...")

    script_path = Path(f"scripts/debug/debug_{component}.py")
    if not script_path.exists():
        print(f"❌ Debug tool for {component} not found")
        raise typer.Exit(1)

    cmd = ["python", str(script_path)]
    if verbose:
        cmd.append("--verbose")

    try:
        subprocess.run(cmd, check=True)
        print("✅ Debug completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Debug failed: {e}")
        raise typer.Exit(1)


@tools_app.command("cleanup")
def tools_cleanup(
    cache: bool = typer.Option(True, "--cache", help="Clean cache files"),
    results: bool = typer.Option(False, "--results", help="Clean old results"),
    temp: bool = typer.Option(True, "--temp", help="Clean temp files"),
) -> None:
    """🧹 System cleanup and maintenance."""
    print("🧹 Running system cleanup...")

    cleaned = []

    if cache:
        cache_dir = Path("cache")
        if cache_dir.exists():
            import shutil

            shutil.rmtree(cache_dir)
            cleaned.append("Cache directory")

    if temp:
        for temp_file in Path(".").glob("temp_*.yaml"):
            temp_file.unlink()
            cleaned.append(f"Temp file: {temp_file.name}")

    if results:
        results_dir = Path("results")
        if results_dir.exists():
            cutoff = time.time() - (30 * 24 * 60 * 60)  # 30 days
            for result_dir in results_dir.glob("*/"):
                if result_dir.stat().st_mtime < cutoff:
                    import shutil

                    shutil.rmtree(result_dir)
                    cleaned.append(f"Old result: {result_dir.name}")

    if cleaned:
        print("✅ Cleanup completed:")
        for item in cleaned:
            print(f"  • {item}")
    else:
        print("ℹ️ Nothing to clean")


if __name__ == "__main__":
    app()
# ruff: noqa: B904, B007, RUF001
