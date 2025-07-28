#!/usr/bin/env python3
"""
Simple static chart generator for backtest visualization demo.
"""

import argparse
import sys
from pathlib import Path

import mplfinance as mpf
import pandas as pd


def create_static_chart(results_dir, output_file=None):
    """Create a static chart from backtest results."""

    results_dir = Path(results_dir)

    # Load required files
    data_file = results_dir / "data.csv"
    trades_file = results_dir / "trades.csv"
    events_file = results_dir / "events.parquet"

    if not data_file.exists():
        print(f"❌ data.csv not found in {results_dir}")
        return False

    # Load market data
    print("📊 Loading market data...")
    df = pd.read_csv(data_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    # Limit data for better visualization (last 200 candles)
    df = df.tail(200)
    print(f"📈 Using {len(df)} candles for visualization")

    # Load trades
    trades_df = None
    if trades_file.exists():
        print("💰 Loading trades...")
        trades_df = pd.read_csv(trades_file)
        trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])
        trades_df["exit_time"] = pd.to_datetime(trades_df["exit_time"])

        # Filter trades to match our data window
        start_time = df.index.min()
        end_time = df.index.max()
        trades_df = trades_df[
            (trades_df["entry_time"] >= start_time)
            & (trades_df["entry_time"] <= end_time)
        ]
        print(f"💼 Found {len(trades_df)} trades in time window")

    # Load events
    events_df = None
    if events_file.exists():
        try:
            print("📋 Loading events...")
            events_df = pd.read_parquet(events_file)
            events_df["timestamp"] = pd.to_datetime(events_df["timestamp"])

            # Filter events to match our data window
            start_time = df.index.min()
            end_time = df.index.max()
            events_df = events_df[
                (events_df["timestamp"] >= start_time)
                & (events_df["timestamp"] <= end_time)
            ]
            print(f"📊 Found {len(events_df)} events in time window")
        except Exception as e:
            print(f"⚠️  Could not load events: {e}")
            events_df = None

    # Create the plot
    print("🎨 Generating chart...")

    # Set up the plot style
    style = mpf.make_mpf_style(
        base_mpl_style="dark_background", gridstyle="-", gridcolor="gray"
    )

    # Prepare additional plots for trades
    additional_plots = []

    if trades_df is not None and len(trades_df) > 0:
        print(f"📍 Adding {len(trades_df)} trade markers")

        # Create a simple line plot showing trade levels
        trade_prices = []
        trade_times = []

        for _, trade in trades_df.iterrows():
            # Add entry points
            if trade["entry_time"] in df.index:
                trade_times.append(trade["entry_time"])
                trade_prices.append(trade["entry_price"])

        if trade_times:
            # Create a series aligned with our data
            trade_series = pd.Series(index=df.index, dtype=float)
            for time, price in zip(trade_times, trade_prices, strict=False):
                if time in trade_series.index:
                    trade_series[time] = price

            # Only add if we have valid data
            if not trade_series.dropna().empty:
                additional_plots.append(
                    mpf.make_addplot(
                        trade_series,
                        type="scatter",
                        marker="o",
                        markersize=50,
                        color="yellow",
                        alpha=0.8,
                    )
                )

    # Set output file
    if output_file is None:
        output_file = results_dir / "visualization_chart.png"
    else:
        output_file = Path(output_file)

    # Create the plot
    try:
        mpf.plot(
            df,
            type="candle",
            style=style,
            title=f"Backtest Results - {results_dir.name}",
            ylabel="Price ($)",
            volume=False,
            addplot=additional_plots if additional_plots else None,
            savefig={"fname": str(output_file), "dpi": 150, "bbox_inches": "tight"},
            show_nontrading=False,
            warn_too_much_data=1000,
        )

        print(f"✅ Chart saved to: {output_file}")
        return True

    except Exception as e:
        print(f"❌ Error creating chart: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate static backtest visualization"
    )
    parser.add_argument("results_dir", nargs="?", help="Results directory to visualize")
    parser.add_argument(
        "--output", "-o", help="Output file path (default: save in results directory)"
    )

    args = parser.parse_args()

    if not args.results_dir:
        print("❌ Please specify a results directory")
        print("Usage: python simple_plot.py <results_directory>")
        sys.exit(1)

    success = create_static_chart(args.results_dir, args.output)

    if not success:
        sys.exit(1)

    print("\n🎉 Visualization complete!")


if __name__ == "__main__":
    main()
