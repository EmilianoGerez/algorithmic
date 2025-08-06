#!/usr/bin/env python3
"""
Simple Backtest Runner
Run backtests with any configuration file.

Usage:
    python3 run_backtest.py --config configs/optimized_btc_20250801.yaml
    python3 run_backtest.py --config configs/optimized_btc_20250801.yaml --verbose
"""

import argparse
import logging
import time
from pathlib import Path

from omegaconf import OmegaConf

from services.models import BacktestConfig
from services.runner import BacktestRunner


def setup_logging(verbose: bool = False):
    """Configure logging for backtest execution."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run_backtest(config_path: str, verbose: bool = False) -> None:
    """Run a single backtest with the given configuration."""

    # Setup logging
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    # Load configuration
    config_path = Path(config_path)
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return

    logger.info(f"Loading configuration from: {config_path}")
    config_dict = OmegaConf.load(config_path)
    config = BacktestConfig(**config_dict)

    logger.info(f"Starting backtest for {config.data.symbol}")
    logger.info(f"Data file: {config.data.path}")
    logger.info(f"Date range: {config.data.start_date} to {config.data.end_date}")
    logger.info(f"Strategy: {config.strategy.name}")

    # Print key parameters
    logger.info("Key Parameters:")
    logger.info(
        f"  Risk per trade: {config.risk.risk_per_trade:.4f} ({config.risk.risk_per_trade * 100:.2f}%)"
    )
    logger.info(f"  Take Profit R:R: {config.risk.tp_rr:.2f}")
    logger.info(f"  Stop Loss ATR: {config.risk.sl_atr_multiple:.2f}x")

    # Run backtest
    start_time = time.time()
    runner = BacktestRunner(config)

    try:
        result = runner.run()
        execution_time = time.time() - start_time

        # Display results
        print("\n" + "=" * 60)
        print("🎉 BACKTEST RESULTS")
        print("=" * 60)

        if result.success and result.metrics:
            metrics = result.metrics

            print("\n📈 Performance Summary:")
            print(f"  Total Return: {metrics.get('total_return', 0) * 100:+.2f}%")
            print(f"  Total PnL: ${metrics.get('total_pnl', 0):,.2f}")
            print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
            print(f"  Max Drawdown: {metrics.get('max_drawdown', 0) * 100:.2f}%")

            print("\n📊 Trading Activity:")
            print(f"  Total Trades: {metrics.get('total_trades', 0)}")
            print(f"  Winning Trades: {metrics.get('winning_trades', 0)}")
            print(f"  Win Rate: {metrics.get('win_rate', 0) * 100:.1f}%")
            print(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")

            print("\n⏱️ Execution:")
            print(f"  Execution Time: {execution_time:.1f}s")
            print(f"  Data Period: {result.data_start} to {result.data_end}")

            if result.result_dir:
                print(f"\n📁 Results saved to: {result.result_dir}")

        else:
            print(f"\n❌ Backtest failed: {result.error_message}")
            logger.error(f"Backtest execution failed: {result.error_message}")

    except Exception as e:
        print(f"\n❌ Error running backtest: {e}")
        logger.error(f"Error running backtest: {e}", exc_info=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run backtest with configuration file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--config", type=str, required=True, help="Path to configuration file (YAML)"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    run_backtest(args.config, args.verbose)


if __name__ == "__main__":
    main()
