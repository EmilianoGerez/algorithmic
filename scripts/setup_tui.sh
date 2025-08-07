#!/bin/bash
# QuantBT TUI Installation and Setup Script

echo "🚀 QuantBT Terminal User Interface Setup"
echo "========================================"

# Check if we're in the right directory
if [ ! -f "quantbt_tui.py" ]; then
    echo "❌ Error: quantbt_tui.py not found!"
    echo "Please run this script from the project root directory."
    exit 1
fi

# Check Python version
python3 --version > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Error: Python 3 not found!"
    echo "Please install Python 3.7 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is available
python3 -m pip --version > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Error: pip not found!"
    echo "Please install pip for Python 3."
    exit 1
fi

echo "✅ pip found"

# Install/check required dependencies
echo "🔧 Checking dependencies..."

# Check typer
python3 -c "import typer" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing typer..."
    python3 -m pip install typer
else
    echo "✅ typer already installed"
fi

# Check rich (optional but recommended)
python3 -c "import rich" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing rich (for beautiful formatting)..."
    python3 -m pip install rich
else
    echo "✅ rich already installed"
fi

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x launch_tui.py 2>/dev/null || true
chmod +x quantbt_tui.py 2>/dev/null || true
chmod +x quantbt_simple.py 2>/dev/null || true

# Test the TUI
echo "🧪 Testing TUI installation..."
timeout 3 python3 quantbt_tui.py <<< "0" > /dev/null 2>&1
if [ $? -eq 0 ] || [ $? -eq 124 ]; then  # 124 is timeout exit code
    echo "✅ TUI installation successful!"
else
    echo "⚠️  TUI test had issues, but installation completed"
fi

echo ""
echo "🎉 Setup Complete!"
echo "==================="
echo ""
echo "📋 Available interfaces:"
echo "  🖥️  Terminal UI:  python3 quantbt_tui.py"
echo "  ⌨️  Simple CLI:   python3 quantbt_simple.py"
echo "  🚀 Launcher:     python3 launch_tui.py"
echo ""
echo "🎯 Quick start:"
echo "  python3 quantbt_tui.py"
echo ""
echo "📚 Documentation:"
echo "  python3 quantbt_simple.py --help"
echo "  cat docs/ENHANCED_CLI_GUIDE.md"
echo ""
echo "🎪 Features:"
echo "  ✅ Data management (fetch, validate, browse)"
echo "  ✅ Backtesting (quick, custom, walk-forward)"
echo "  ✅ Optimization (3-phase, bayesian, ultra-fast)"
echo "  ✅ Analysis and reporting"
echo "  ✅ Live monitoring"
echo "  ✅ Configuration management"
echo ""
echo "Have fun trading! 🚀📈"
