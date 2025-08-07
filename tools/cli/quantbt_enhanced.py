#!/usr/bin/env python3
"""
QuantBT Enhanced CLI Entry Point

This is a placeholder for enhanced CLI functionality.
Currently redirects to the main CLI interface.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def main():
    """Main entry point for enhanced CLI."""
    print("🎯 QuantBT Enhanced CLI")
    print("Currently redirecting to main CLI...")

    # Import and run the main CLI
    from tools.cli.quantbt_simple import main as simple_main

    simple_main()


if __name__ == "__main__":
    main()
