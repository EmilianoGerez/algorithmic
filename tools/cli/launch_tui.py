#!/usr/bin/env python3
"""
QuantBT TUI Launcher
Simple launcher that works with or without rich formatting.
"""

import subprocess
import sys
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are available."""
    missing = []

    try:
        import typer
    except ImportError:
        missing.append("typer")

    return missing


def install_dependencies(packages):
    """Install missing dependencies."""
    print("🔧 Installing missing dependencies...")
    for package in packages:
        print(f"Installing {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {package}")
            return False
    return True


def main():
    """Main launcher."""
    print("🚀 QuantBT Terminal User Interface")
    print("=" * 40)

    # Check dependencies
    missing = check_dependencies()
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        install = input("Install missing dependencies? (y/N): ").strip().lower() == "y"
        if install:
            if not install_dependencies(missing):
                print("❌ Failed to install dependencies. Please install manually:")
                for pkg in missing:
                    print(f"  pip install {pkg}")
                sys.exit(1)
        else:
            print("❌ Cannot continue without dependencies.")
            sys.exit(1)

    # Check if TUI script exists
    tui_script = Path("quantbt_tui.py")
    if not tui_script.exists():
        print("❌ TUI script not found!")
        sys.exit(1)

    # Launch TUI
    print("🎯 Launching Terminal User Interface...")
    try:
        subprocess.run([sys.executable, str(tui_script)])
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error launching TUI: {e}")


if __name__ == "__main__":
    main()
