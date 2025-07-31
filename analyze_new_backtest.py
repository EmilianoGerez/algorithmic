#!/usr/bin/env python3
"""Analyze the new backtest results to confirm entry spacing is working."""

import json
from datetime import datetime
from pathlib import Path


def analyze_new_backtest():
    """Analyze the most recent backtest for entry spacing validation."""

    # Find most recent backtest results
    results_dir = Path("results")
    if not results_dir.exists():
        print("❌ No results directory found")
        return

    backtest_dirs = sorted(
        [d for d in results_dir.iterdir() if d.name.startswith("backtest_20250730_22")]
    )
    if not backtest_dirs:
        print("❌ No backtest results found")
        return

    latest_dir = backtest_dirs[-1]
    trades_file = latest_dir / "all_trades.json"

    if not trades_file.exists():
        print(f"❌ No trades file found in {latest_dir}")
        return

    print(f"=== Analyzing Backtest Results: {latest_dir.name} ===")

    # Load and analyze trades
    with open(trades_file) as f:
        trades = json.load(f)

    print(f"Total trades: {len(trades)}")

    # Parse timestamps and analyze timing
    entry_times = []
    for trade in trades:
        trade_id = trade.get("trade_id", "?")
        entry_time_str = trade.get("entry_time", "")
        if entry_time_str:
            try:
                # Parse various timestamp formats
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d %H:%M:%S",
                ]:
                    try:
                        entry_time = datetime.strptime(entry_time_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # Try parsing as ISO format
                    entry_time = datetime.fromisoformat(
                        entry_time_str.replace("Z", "+00:00")
                    )

                entry_times.append((trade_id, entry_time))
                print(f"Trade {trade_id}: {entry_time}")
            except Exception as e:
                print(
                    f"❌ Failed to parse time for trade {trade_id}: {entry_time_str} - {e}"
                )

    # Analyze time gaps
    if len(entry_times) > 1:
        print("\n=== Entry Spacing Analysis ===")
        entry_times.sort(key=lambda x: x[1])

        rapid_fire_count = 0
        proper_spacing_count = 0

        for i in range(1, len(entry_times)):
            prev_trade, prev_time = entry_times[i - 1]
            curr_trade, curr_time = entry_times[i]

            time_gap = curr_time - prev_time
            gap_minutes = time_gap.total_seconds() / 60

            status = (
                "✅ PROPER"
                if gap_minutes >= 30
                else "⚠️  CLOSE"
                if gap_minutes >= 10
                else "❌ RAPID"
            )
            if gap_minutes < 1:
                rapid_fire_count += 1
            elif gap_minutes >= 30:
                proper_spacing_count += 1

            print(f"{prev_trade} → {curr_trade}: {gap_minutes:.1f} minutes {status}")

        print("\n=== Summary ===")
        print(f"Rapid-fire entries (< 1 min): {rapid_fire_count}")
        print(f"Proper spacing (≥ 30 min): {proper_spacing_count}")
        print(f"Total gaps analyzed: {len(entry_times) - 1}")

        if rapid_fire_count == 0:
            print("✅ SUCCESS: No rapid-fire entries detected!")
            print("✅ Entry spacing mechanism is working correctly!")
        else:
            print(
                "❌ ISSUE: Found rapid-fire entries - mechanism may not be fully working"
            )
    else:
        print("Not enough trades to analyze spacing")


if __name__ == "__main__":
    analyze_new_backtest()
