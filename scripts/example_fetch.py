#!/usr/bin/env python3
"""
Quick example script showing how to use fetch_crypto_data.py
"""

import subprocess
import sys
from pathlib import Path


def run_fetch_example() -> None:
    """Run an example data fetch for BTC/USD."""
    script_path = Path(__file__).parent / "fetch_crypto_data.py"

    # Example command to fetch BTC/USD 5-minute data for 2 months
    cmd = [
        sys.executable,
        str(script_path),
        "--symbol",
        "BTC/USD",
        "--timeframe",
        "5min",
        "--start",
        "2025-05-01",
        "--end",
        "2025-07-01",
        "--output",
        "data",
    ]

    print("Running example data fetch:")
    print(" ".join(cmd))
    print()

    try:
        subprocess.run(cmd, check=True, capture_output=False)
        print("\nExample completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error running example: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_fetch_example()
