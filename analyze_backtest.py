#!/usr/bin/env python3
"""
Backtest Results Analysis Tool

Professional analysis tool for HTF Liquidity Strategy backtest results.
Generates comprehensive visualizations and trade summaries.

Usage:
    python3 analyze_backtest.py                           # Use latest results
    python3 analyze_backtest.py results/backtest_folder   # Specific folder
    python3 analyze_backtest.py --list                    # List available results
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# Add project root to path
sys.path.append(str(Path(__file__).parent))

try:
    from quant_algo.visual.enhanced_analysis import (
        create_enhanced_trading_plot,
        export_trade_summary,
    )
except ImportError:
    print(
        "❌ Error: Enhanced analysis module not found. Please ensure quant_algo package is properly installed."
    )
    sys.exit(1)


class BacktestAnalyzer:
    """Professional backtest analysis tool."""

    def __init__(self, results_path: str | None = None):
        """Initialize analyzer with results path.

        Args:
            results_path: Path to backtest results folder
        """
        self.results_dir = self._get_results_directory(results_path)

    def _get_results_directory(self, results_path: str | None) -> Path:
        """Get the target results directory.

        Args:
            results_path: Optional path to specific results directory

        Returns:
            Path to the target directory

        Raises:
            SystemExit: If directory doesn't exist or no results found
        """
        if results_path:
            target_path = Path(results_path)
            if not target_path.exists() or not target_path.is_dir():
                print(f"❌ Error: Directory does not exist: {target_path}")
                sys.exit(1)

            # Check if it has required files
            if not self._validate_results_directory(target_path):
                print(
                    f"❌ Error: Invalid results directory (missing data.csv): {target_path}"
                )
                sys.exit(1)

            print(f"📁 Analyzing: {target_path}")
            return target_path

        # Find latest backtest results
        results_base = Path("results")
        if not results_base.exists():
            print("❌ Error: No 'results' directory found. Run a backtest first.")
            sys.exit(1)

        backtest_dirs = [
            d
            for d in results_base.iterdir()
            if d.is_dir()
            and d.name.startswith("backtest_")
            and self._validate_results_directory(d)
        ]

        if not backtest_dirs:
            print("❌ Error: No valid backtest results found in 'results' directory.")
            sys.exit(1)

        # Use most recent
        latest_dir = max(backtest_dirs, key=lambda d: d.name)
        print(f"📁 Using latest results: {latest_dir}")
        return latest_dir

    def _validate_results_directory(self, path: Path) -> bool:
        """Validate that directory contains required files.

        Args:
            path: Directory path to validate

        Returns:
            True if directory is valid
        """
        return (path / "data.csv").exists()

    def analyze(
        self, export_formats: list[str] | None = None, show_plot: bool = True
    ) -> dict[str, Any]:
        """Run comprehensive analysis on backtest results.

        Args:
            export_formats: List of export formats ('csv', 'json', 'excel')
            show_plot: Whether to display interactive plot

        Returns:
            Analysis results dictionary
        """
        if export_formats is None:
            export_formats = ["csv", "json", "excel"]

        print("\n🔍 ANALYZING BACKTEST RESULTS")
        print(f"📂 Directory: {self.results_dir}")
        print(f"📊 Export formats: {', '.join(export_formats)}")
        print("=" * 60)

        # Load market data
        data_path = self.results_dir / "data.csv"
        print(f"📈 Loading market data from: {data_path.name}")
        data_df = pd.read_csv(data_path)
        print(f"   → {len(data_df):,} data points loaded")

        # Load trades data
        trades_data = self._load_trades_data()
        open_positions = self._load_open_positions()

        # Load events data
        events_df = self._load_events_data()

        # Create enhanced visualization
        print("\n📊 Creating enhanced trading plot...")
        fig = create_enhanced_trading_plot(
            data_df=data_df,
            trades_data=trades_data,
            open_positions=open_positions,
            events_df=events_df,
            title=f"HTF Liquidity Strategy Analysis - {self.results_dir.name}",
            output_dir=self.results_dir,
        )

        if show_plot:
            print("🖥️  Opening interactive plot...")
            fig.show()

        # Export trade summaries
        print("\n📋 Exporting trade summaries...")
        exported_files = export_trade_summary(
            trades_data=trades_data,
            open_positions=open_positions,
            output_dir=self.results_dir,
            formats=export_formats,
        )

        # Compile results
        results = {
            "results_directory": str(self.results_dir),
            "data_points": len(data_df),
            "total_trades": len(trades_data) if trades_data else 0,
            "open_positions": len(open_positions) if open_positions else 0,
            "exported_files": {fmt: str(path) for fmt, path in exported_files.items()},
            "analysis_timestamp": pd.Timestamp.now().isoformat(),
        }

        # Print summary
        self._print_analysis_summary(results)

        return results

    def _load_trades_data(self) -> list[dict[str, Any]] | None:
        """Load trades data from JSON file.

        Returns:
            List of trade dictionaries or None
        """
        trades_path = self.results_dir / "trades.json"
        if not trades_path.exists():
            print("   → No trades.json found")
            return None

        try:
            with open(trades_path) as f:
                trades_data = json.load(f)
            print(f"   → {len(trades_data)} trades loaded from {trades_path.name}")
            return trades_data
        except Exception as e:
            print(f"   → Error loading trades: {e}")
            return None

    def _load_open_positions(self) -> list[dict[str, Any]] | None:
        """Load open positions data from JSON file.

        Returns:
            List of position dictionaries or None
        """
        positions_path = self.results_dir / "open_positions.json"
        if not positions_path.exists():
            print("   → No open_positions.json found")
            return None

        try:
            with open(positions_path) as f:
                positions_data = json.load(f)
            print(
                f"   → {len(positions_data)} open positions loaded from {positions_path.name}"
            )
            return positions_data
        except Exception as e:
            print(f"   → Error loading open positions: {e}")
            return None

    def _load_events_data(self) -> pd.DataFrame | None:
        """Load events data from parquet file.

        Returns:
            Events DataFrame or None
        """
        events_path = self.results_dir / "events.parquet"
        if not events_path.exists():
            print("   → No events.parquet found")
            return None

        try:
            events_df = pd.read_parquet(events_path)
            print(f"   → {len(events_df)} events loaded from {events_path.name}")
            return events_df
        except Exception as e:
            print(f"   → Error loading events: {e}")
            return None

    def _print_analysis_summary(self, results: dict[str, Any]) -> None:
        """Print analysis summary.

        Args:
            results: Analysis results dictionary
        """
        print("\n" + "=" * 60)
        print("✅ ANALYSIS COMPLETE")
        print("=" * 60)
        print(f"📂 Results directory: {Path(results['results_directory']).name}")
        print(f"📈 Market data points: {results['data_points']:,}")
        print(f"💼 Total trades: {results['total_trades']}")
        print(f"📍 Open positions: {results['open_positions']}")
        print(f"📋 Files exported: {len(results['exported_files'])}")
        for fmt, path in results["exported_files"].items():
            print(f"   → {fmt.upper()}: {Path(path).name}")
        print("=" * 60)


def list_available_results() -> None:
    """List all available backtest results directories."""
    results_dir = Path("results")
    if not results_dir.exists():
        print("❌ No 'results' directory found.")
        return

    backtest_dirs = [
        d
        for d in results_dir.iterdir()
        if d.is_dir() and d.name.startswith("backtest_")
    ]

    if not backtest_dirs:
        print("❌ No backtest directories found.")
        return

    print("📁 Available backtest results:")
    for i, directory in enumerate(sorted(backtest_dirs, key=lambda d: d.name), 1):
        # Get directory size
        size_mb = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file()) / (
            1024 * 1024
        )

        # Check if valid
        is_valid = (directory / "data.csv").exists()
        status = "✅" if is_valid else "❌"

        print(f"   {i:2d}. {directory.name} ({size_mb:.1f} MB) {status}")

    # Show latest
    latest = max(backtest_dirs, key=lambda d: d.name)
    print(f"\nLatest: {latest.name}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze HTF Liquidity Strategy backtest results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 analyze_backtest.py                           # Latest results
  python3 analyze_backtest.py results/backtest_20250730  # Specific folder
  python3 analyze_backtest.py --list                    # List available
        """,
    )

    parser.add_argument(
        "results_path", nargs="?", help="Path to backtest results directory"
    )
    parser.add_argument(
        "--list", action="store_true", help="List available backtest results"
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["csv", "json", "excel"],
        default=["csv", "json", "excel"],
        help="Export formats (default: csv json excel)",
    )
    parser.add_argument(
        "--no-plot", action="store_true", help="Skip showing interactive plot"
    )

    args = parser.parse_args()

    if args.list:
        list_available_results()
        return

    try:
        analyzer = BacktestAnalyzer(args.results_path)
        analyzer.analyze(export_formats=args.formats, show_plot=not args.no_plot)
    except KeyboardInterrupt:
        print("\n⏹️  Analysis cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
