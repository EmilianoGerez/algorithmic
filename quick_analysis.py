#!/usr/bin/env python3
"""
Quick Backtest Analysis Helper

Simple interactive helper for running backtest analysis.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Interactive helper for backtest analysis."""
    print("🚀 HTF LIQUIDITY STRATEGY - BACKTEST ANALYSIS")
    print("=" * 50)

    while True:
        print("\nWhat would you like to do?")
        print("  1. Analyze latest backtest results")
        print("  2. List all available results")
        print("  3. Analyze specific results folder")
        print("  4. Show help")
        print("  5. Exit")

        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == "1":
            print("\n🔍 Running analysis on latest results...")
            subprocess.run([sys.executable, "analyze_backtest.py"])

        elif choice == "2":
            print("\n📁 Available backtest results:")
            subprocess.run([sys.executable, "analyze_backtest.py", "--list"])

        elif choice == "3":
            folder = input("\nEnter results folder path: ").strip()
            if folder:
                print(f"\n🔍 Running analysis on: {folder}")
                subprocess.run([sys.executable, "analyze_backtest.py", folder])
            else:
                print("❌ No folder specified")

        elif choice == "4":
            print("\n📖 USAGE HELP:")
            print("=" * 30)
            print("Direct usage:")
            print(
                "  python3 analyze_backtest.py                           # Latest results"
            )
            print(
                "  python3 analyze_backtest.py results/backtest_folder   # Specific folder"
            )
            print(
                "  python3 analyze_backtest.py --list                    # List available"
            )
            print("  python3 analyze_backtest.py --help                    # Full help")
            print("\nInteractive helper:")
            print(
                "  python3 quick_analysis.py                             # This script"
            )

        elif choice == "5":
            print("\n👋 Goodbye!")
            break

        else:
            print("❌ Invalid choice. Please enter 1-5.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
