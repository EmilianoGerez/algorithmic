#!/usr/bin/env python3
"""
QuantBT Project Launcher

Simple script to launch the QuantBT Terminal User Interface.
This is the main entry point for the project.

Usage:
    ./quantbt                    # Launch TUI
    ./quantbt --help            # Show help
    ./quantbt --test            # Run tests
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Main launcher function."""
    project_root = Path(__file__).parent

    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print_help()
            return 0
        elif sys.argv[1] == "--test":
            return run_tests()
        elif sys.argv[1] == "--version":
            print("QuantBT v2.0.0")
            return 0

    # Launch TUI
    try:
        tui_path = project_root / "tools" / "cli" / "quantbt_tui.py"
        if not tui_path.exists():
            print("❌ Error: TUI not found at expected location")
            print(f"   Expected: {tui_path}")
            return 1

        os.chdir(project_root)
        result = subprocess.run([sys.executable, str(tui_path)])
        return result.returncode

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 0
    except Exception as e:
        print(f"❌ Error launching TUI: {e}")
        return 1


def print_help():
    """Print help information."""
    print("""
🎯 QuantBT - Quantitative Trading Platform

Usage:
    ./quantbt           Launch the Terminal User Interface
    ./quantbt --test    Run all tests
    ./quantbt --help    Show this help
    ./quantbt --version Show version

Features:
    🎨 Beautiful terminal interface
    📊 Data management and validation
    🎯 Backtesting and optimization
    📈 Visualization and analysis
    ⚙️  Configuration management
    📡 Live monitoring

Directory Structure:
    tools/cli/          CLI and TUI applications
    tests/cli/          CLI/TUI tests
    scripts/            Setup and utility scripts
    docs/               Documentation

For more information, see docs/README.md
""")


def run_tests():
    """Run the test suite."""
    print("🧪 Running QuantBT test suite...")

    project_root = Path(__file__).parent
    test_runner = project_root / "tests" / "run_all_tests.py"

    if not test_runner.exists():
        print(f"❌ Test runner not found: {test_runner}")
        return 1

    try:
        result = subprocess.run([sys.executable, str(test_runner)], cwd=project_root)
        return result.returncode
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
