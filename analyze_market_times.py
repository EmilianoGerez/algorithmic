#!/usr/bin/env python3
"""Analyze entry spacing from log data showing actual market times."""

from datetime import datetime


def analyze_log_entry_times():
    """Analyze the actual market entry times from the log messages."""

    # Extract actual market entry times from the logs
    entry_times = [
        ("Trade 1", datetime(2025, 5, 19, 14, 15)),  # 2025-05-19 14:15:00
        ("Trade 2", datetime(2025, 5, 20, 8, 50)),  # 2025-05-20 08:50:00
        ("Trade 3", datetime(2025, 5, 20, 11, 30)),  # 2025-05-20 11:30:00
        ("Trade 4", datetime(2025, 5, 20, 14, 20)),  # 2025-05-20 14:20:00
        (
            "Trade 5",
            datetime(2025, 5, 20, 14, 20),
        ),  # 2025-05-20 14:20:00 (same zone, same time)
        ("Trade 6", datetime(2025, 5, 20, 16, 10)),  # 2025-05-20 16:10:00
        ("Trade 7", datetime(2025, 5, 20, 17, 10)),  # 2025-05-20 17:10:00
    ]

    print("=== Entry Spacing Analysis (Market Times) ===")
    print(f"Total trades: {len(entry_times)}")

    for trade_id, entry_time in entry_times:
        print(f"{trade_id}: {entry_time}")

    print("\n=== Time Gap Analysis ===")

    rapid_fire_count = 0
    proper_spacing_count = 0
    good_spacing_count = 0

    for i in range(1, len(entry_times)):
        prev_trade, prev_time = entry_times[i - 1]
        curr_trade, curr_time = entry_times[i]

        time_gap = curr_time - prev_time
        gap_minutes = time_gap.total_seconds() / 60
        gap_hours = gap_minutes / 60

        if gap_minutes >= 30:
            status = "✅ PROPER (≥30m)"
            proper_spacing_count += 1
        elif gap_minutes >= 10:
            status = "⚠️  GOOD (≥10m)"
            good_spacing_count += 1
        elif gap_minutes < 1:
            status = "❌ RAPID (<1m)"
            rapid_fire_count += 1
        else:
            status = "⚠️  CLOSE"

        if gap_hours >= 1:
            print(f"{prev_trade} → {curr_trade}: {gap_hours:.1f} hours {status}")
        else:
            print(f"{prev_trade} → {curr_trade}: {gap_minutes:.1f} minutes {status}")

    print("\n=== Summary ===")
    print(f"Rapid-fire entries (< 1 min): {rapid_fire_count}")
    print(f"Good spacing (10-29 min): {good_spacing_count}")
    print(f"Proper spacing (≥ 30 min): {proper_spacing_count}")
    print(f"Total gaps analyzed: {len(entry_times) - 1}")

    # Additional analysis
    unique_times = list({t[1] for t in entry_times})
    simultaneous_entries = len(entry_times) - len(unique_times)

    print("\n=== Advanced Analysis ===")
    print(f"Unique entry times: {len(unique_times)}")
    print(f"Simultaneous entries (same zone, same time): {simultaneous_entries}")

    if rapid_fire_count == 0:
        print("\n✅ SUCCESS: No rapid-fire entries detected!")
        print("✅ Entry spacing mechanism is working correctly!")
        print(
            "✅ The mechanism properly enforces 30-minute spacing between pool entries!"
        )
    else:
        print(f"\n❌ ISSUE: Found {rapid_fire_count} rapid-fire entries")

    # Check per-pool spacing
    print("\n=== Per-Pool Analysis ===")
    pool_entries = {
        "H4_2025-05-19T08:00:00+00:00_6998085b": [entry_times[0]],  # Trade 1
        "H4_2025-05-19T20:00:00+00:00_5fc807bc": [
            entry_times[1],
            entry_times[2],
        ],  # Trade 2, 3
        "H4_2025-05-19T16:00:00+00:00_790a09e5": [
            entry_times[3],
            entry_times[4],
        ],  # Trade 4, 5
        "H4_2025-05-20T08:00:00+00:00_73bf0a1f": [
            entry_times[5],
            entry_times[6],
        ],  # Trade 6, 7
    }

    for pool_id, trades in pool_entries.items():
        print(f"\nPool: {pool_id}")
        for i, (trade_id, time) in enumerate(trades):
            print(f"  {trade_id}: {time}")
            if i > 0:
                prev_time = trades[i - 1][1]
                gap = (time - prev_time).total_seconds() / 60
                status = "✅" if gap >= 30 else "❌"
                print(f"    Gap from previous: {gap:.1f} minutes {status}")


if __name__ == "__main__":
    analyze_log_entry_times()
