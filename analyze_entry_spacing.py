#!/usr/bin/env python3
"""
Test script to verify entry spacing in backtest configuration.
"""

import json
from collections import defaultdict
from datetime import datetime


def analyze_trade_spacing(trades_file):
    """Analyze trade spacing from backtest results."""

    try:
        with open(trades_file) as f:
            trades = json.load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {trades_file}")
        return
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in file: {trades_file}")
        return

    if not trades:
        print("❌ No trades found in backtest results")
        return

    print(f"📊 Analyzing {len(trades)} trades for entry spacing...")
    print("=" * 60)

    # Sort trades by entry time
    trades_sorted = sorted(trades, key=lambda t: t["entry_time"])

    # Parse entry times
    entry_times = []
    for trade in trades_sorted:
        try:
            # Handle different datetime formats
            entry_str = trade["entry_time"]
            if "+" in entry_str:
                # Remove timezone info for parsing
                entry_str = entry_str.split("+")[0]

            entry_time = datetime.fromisoformat(entry_str)
            entry_times.append(
                {
                    "id": trade["id"],
                    "time": entry_time,
                    "price": trade["entry_price"],
                    "side": trade["side"],
                }
            )
        except Exception as e:
            print(
                f"⚠️  Could not parse entry time for trade {trade.get('id', 'unknown')}: {e}"
            )

    if len(entry_times) < 2:
        print("⚠️  Need at least 2 trades to analyze spacing")
        return

    # Analyze spacing violations
    spacing_violations = []
    rapid_fire_groups = []

    for i in range(1, len(entry_times)):
        prev_trade = entry_times[i - 1]
        curr_trade = entry_times[i]

        time_diff = curr_trade["time"] - prev_trade["time"]
        seconds_diff = time_diff.total_seconds()
        minutes_diff = seconds_diff / 60

        print(
            f"Trade {prev_trade['id']} → {curr_trade['id']}: {minutes_diff:.2f} minutes apart"
        )

        # Check for violations (should be at least 10 minutes globally)
        if minutes_diff < 10:  # Global minimum spacing
            spacing_violations.append(
                {
                    "trade1": prev_trade,
                    "trade2": curr_trade,
                    "gap_minutes": minutes_diff,
                    "gap_seconds": seconds_diff,
                }
            )

        # Check for rapid-fire (less than 1 minute)
        if seconds_diff < 60:
            rapid_fire_groups.append(
                {
                    "trade1": prev_trade,
                    "trade2": curr_trade,
                    "gap_seconds": seconds_diff,
                }
            )

    print("\n🚨 ANALYSIS RESULTS:")
    print("=" * 40)

    if spacing_violations:
        print(
            f"❌ ENTRY SPACING VIOLATIONS: {len(spacing_violations)} violations found"
        )
        print("   Minimum global spacing should be 10 minutes")

        for violation in spacing_violations[:5]:  # Show first 5
            gap = violation["gap_minutes"]
            print(
                f"   • {violation['trade1']['id']} → {violation['trade2']['id']}: {gap:.2f} minutes (< 10 min required)"
            )

        if len(spacing_violations) > 5:
            print(f"   ... and {len(spacing_violations) - 5} more violations")
    else:
        print("✅ NO SPACING VIOLATIONS: All trades respect 10+ minute global spacing")

    if rapid_fire_groups:
        print(
            f"\n🔥 RAPID-FIRE TRADES: {len(rapid_fire_groups)} trades within 1 minute"
        )
        for group in rapid_fire_groups[:5]:  # Show first 5
            gap = group["gap_seconds"]
            print(
                f"   • {group['trade1']['id']} → {group['trade2']['id']}: {gap:.1f} seconds apart"
            )

        if len(rapid_fire_groups) > 5:
            print(f"   ... and {len(rapid_fire_groups) - 5} more rapid-fire trades")
    else:
        print("✅ NO RAPID-FIRE TRADES: All entries are spaced > 1 minute apart")

    # Summary statistics
    if spacing_violations:
        min_gap = min(v["gap_minutes"] for v in spacing_violations)
        print("\n📈 SPACING STATISTICS:")
        print(f"   Minimum gap: {min_gap:.2f} minutes")
        print(
            f"   Violations: {len(spacing_violations)}/{len(entry_times) - 1} trade pairs"
        )
        print(
            f"   Success rate: {((len(entry_times) - 1 - len(spacing_violations)) / (len(entry_times) - 1) * 100):.1f}%"
        )

    return len(spacing_violations) == 0


def main():
    """Main analysis function."""

    # Check the recent backtest results
    trades_file = "results/backtest_20250730_214510/all_trades.json"

    print("🔍 ENTRY SPACING ANALYSIS")
    print("=" * 60)
    print(f"📁 Analyzing: {trades_file}")
    print()

    success = analyze_trade_spacing(trades_file)

    if success:
        print("\n🎉 ENTRY SPACING IS WORKING CORRECTLY!")
    else:
        print("\n⚠️  ENTRY SPACING NEEDS ATTENTION!")
        print("\n💡 RECOMMENDATIONS:")
        print("   1. Verify ZoneWatcher configuration includes entry spacing")
        print("   2. Check that SignalCandidate FSM calls ready_callback")
        print("   3. Ensure config is properly loaded in backtest")
        print("   4. Re-run backtest with corrected configuration")


if __name__ == "__main__":
    main()
