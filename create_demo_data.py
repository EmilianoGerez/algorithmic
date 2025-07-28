#!/usr/bin/env python3
"""
Demo script to create mock backtest data files for visualization testing.
This demonstrates the complete visualization workflow with realistic data.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def create_mock_backtest_data(results_dir: Path, data_file: str) -> bool:
    """Create mock backtest data files for visualization testing."""

    results_dir = Path(results_dir)
    results_dir.mkdir(exist_ok=True)

    print(f"📁 Creating mock backtest data in: {results_dir}")

    # Load the real market data
    data_path = Path(data_file)
    if not data_path.exists():
        print(f"❌ Data file not found: {data_file}")
        return False

    print(f"📊 Loading market data from: {data_file}")
    market_df = pd.read_csv(data_path)

    # Take a subset for demo (first 1000 candles)
    market_df = market_df.head(1000).copy()
    market_df["timestamp"] = pd.to_datetime(market_df["timestamp"])

    # 1. Create data.csv (market data)
    data_csv = results_dir / "data.csv"
    market_df.to_csv(data_csv, index=False)
    print(f"✅ Created data.csv with {len(market_df)} candles")

    # 2. Create trades.csv (mock trades)
    trades: list[dict[str, Any]] = []

    # Generate realistic trades every 20-50 candles
    for i in range(10, len(market_df), np.random.randint(20, 50)):
        if i + 10 < len(market_df):
            entry_time = market_df.iloc[i]["timestamp"]
            entry_price = market_df.iloc[i]["close"]

            # Random trade duration (5-15 candles)
            duration = np.random.randint(5, 15)
            exit_idx = min(i + duration, len(market_df) - 1)
            exit_time = market_df.iloc[exit_idx]["timestamp"]
            exit_price = market_df.iloc[exit_idx]["close"]

            # Calculate PnL (add some randomness for realism)
            price_move = exit_price - entry_price
            size = np.random.uniform(0.1, 2.0)  # Random position size
            pnl = price_move * size

            # Add some trading costs
            pnl -= abs(entry_price * size * 0.001)  # 0.1% trading fee

            # Determine reason
            reason = "take_profit" if pnl > 0 else "stop_loss"
            if abs(pnl) < entry_price * size * 0.005:  # Small moves
                reason = "timeout"

            trades.append(
                {
                    "trade_id": f"trade_{len(trades) + 1}",
                    "entry_time": entry_time,
                    "exit_time": exit_time,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "size": size,
                    "side": "long",  # For simplicity, all long trades
                    "pnl": pnl,
                    "reason": reason,
                    "fees": abs(entry_price * size * 0.001),
                }
            )

    trades_df = pd.DataFrame(trades)
    trades_csv = results_dir / "trades.csv"
    trades_df.to_csv(trades_csv, index=False)
    print(f"✅ Created trades.csv with {len(trades_df)} trades")

    # 3. Create events.parquet (FVG and pivot events)
    events = []

    # Generate FVG events every 30-80 candles
    for i in range(20, len(market_df), np.random.randint(30, 80)):
        if i + 3 < len(market_df):
            # FVG detection logic (simplified)
            candle1 = market_df.iloc[i - 1]
            candle2 = market_df.iloc[i]
            candle3 = market_df.iloc[i + 1]

            # Bullish FVG: gap between candle1 high and candle3 low
            if candle1["high"] < candle3["low"]:
                events.append(
                    {
                        "timestamp": candle2["timestamp"],
                        "type": "fvg",
                        "direction": "bullish",
                        "high": candle3["low"],
                        "low": candle1["high"],
                        "price": (candle1["high"] + candle3["low"]) / 2,
                    }
                )

            # Bearish FVG: gap between candle1 low and candle3 high
            elif candle1["low"] > candle3["high"]:
                events.append(
                    {
                        "timestamp": candle2["timestamp"],
                        "type": "fvg",
                        "direction": "bearish",
                        "high": candle1["low"],
                        "low": candle3["high"],
                        "price": (candle1["low"] + candle3["high"]) / 2,
                    }
                )

    # Generate pivot events
    for i in range(50, len(market_df), np.random.randint(40, 100)):
        pivot_type = "high" if np.random.random() > 0.5 else "low"
        events.append(
            {
                "timestamp": market_df.iloc[i]["timestamp"],
                "type": "pivot",
                "direction": pivot_type,
                "high": market_df.iloc[i]["high"]
                if pivot_type == "high"
                else market_df.iloc[i]["close"],
                "low": market_df.iloc[i]["low"]
                if pivot_type == "low"
                else market_df.iloc[i]["close"],
                "price": market_df.iloc[i]["high"]
                if pivot_type == "high"
                else market_df.iloc[i]["low"],
            }
        )

    events_df = pd.DataFrame(events)
    if len(events_df) > 0:
        events_parquet = results_dir / "events.parquet"
        events_df.to_parquet(events_parquet, index=False)
        print(f"✅ Created events.parquet with {len(events_df)} events")
    else:
        print("⚠️  No events generated")

    # 4. Create config.yaml and provenance.json (for completeness)
    config_yaml = results_dir / "config.yaml"
    with open(config_yaml, "w") as f:
        f.write("""# Mock backtest configuration
data:
  source: csv
  symbol: BTCUSD
  timeframe: 5m
runtime:
  dump_events: true
  export_data_for_viz: true
strategy:
  name: demo_strategy
""")

    provenance_json = results_dir / "provenance.json"
    with open(provenance_json, "w") as f:
        f.write('{"mock": true, "created_for": "visualization_demo"}')

    print("✅ Created config.yaml and provenance.json")

    # Summary
    print("\n🎯 Mock backtest data created successfully!")
    print(f"📈 Market data: {len(market_df)} candles")
    print(f"💰 Trades: {len(trades_df)} trades")
    print(f"📊 Events: {len(events_df)} events")
    print(f"📁 Location: {results_dir}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create mock backtest data for visualization testing"
    )
    parser.add_argument(
        "--data",
        "-d",
        type=str,
        default="data/BTC_USD_5min_20250728_015400.csv",
        help="Source data file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="results/demo_backtest_20250728_visualization",
        help="Output directory for mock backtest data",
    )

    args = parser.parse_args()

    # Create the mock data
    success = create_mock_backtest_data(args.output, args.data)

    if success:
        print("\n🚀 Now you can test visualization with:")
        print(f"   .venv/bin/python scripts/plot_static.py {args.output}")
        print("\n📊 Or view the interactive chart:")
        print('   .venv/bin/python -c "')
        print("from quant_algo.visual.plot_builder import build_plotly_from_data")
        print("import pandas as pd")
        print(f"data_df = pd.read_csv('{args.output}/data.csv')")
        print(f"trades_df = pd.read_csv('{args.output}/trades.csv')")
        print(f"events_df = pd.read_parquet('{args.output}/events.parquet')")
        print("fig = build_plotly_from_data(data_df, trades_df, events_df)")
        print('fig.show()"')
    else:
        print("❌ Failed to create mock data")
        sys.exit(1)


if __name__ == "__main__":
    main()
