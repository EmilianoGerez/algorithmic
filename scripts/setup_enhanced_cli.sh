#!/bin/bash
"""
Enhanced QuantBT Setup Script

This script sets up the enhanced CLI interface and installs necessary dependencies
for the comprehensive quantitative trading platform.
"""

set -e  # Exit on any error

echo "🚀 Setting up Enhanced QuantBT CLI..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Run this script from the project root directory"
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Error: Python 3.11+ required, found Python $python_version"
    exit 1
fi

echo "✅ Python $python_version detected"

# Create or activate virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install core dependencies
echo "📦 Installing core dependencies..."
pip install -e .

# Install optional dependencies for enhanced features
echo "📦 Installing enhanced features..."
pip install rich typer optuna plotly matplotlib seaborn

# Install development dependencies
echo "🛠️ Installing development tools..."
pip install ruff mypy pytest pre-commit

# Make the enhanced CLI executable
echo "🔧 Setting up enhanced CLI..."
chmod +x quantbt_enhanced.py

# Create symlink for easy access (if not exists)
if [ ! -f "/usr/local/bin/quantbt-enhanced" ]; then
    echo "🔗 Creating global command link..."
    # Create a wrapper script instead of direct symlink for better compatibility
    cat > ~/.local/bin/quantbt-enhanced << EOF
#!/bin/bash
cd "$(dirname "$(readlink -f "\$0")")/../../../Projects/python/algorithmic" || exit 1
source .venv/bin/activate
python quantbt_enhanced.py "\$@"
EOF
    chmod +x ~/.local/bin/quantbt-enhanced

    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
        echo "📝 Added ~/.local/bin to PATH (restart shell to take effect)"
    fi
fi

# Setup pre-commit hooks
if [ -f ".pre-commit-config.yaml" ]; then
    echo "🪝 Setting up pre-commit hooks..."
    pre-commit install
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data results configs cache
mkdir -p results/{phase1_random,phase2_focused,phase3_bayesian}

# Test the enhanced CLI
echo "🧪 Testing enhanced CLI..."
python quantbt_enhanced.py --version

echo ""
echo "✅ Enhanced QuantBT CLI setup completed!"
echo ""
echo "🎯 Quick Start Commands:"
echo "  • python quantbt_enhanced.py                    - Show welcome panel"
echo "  • python quantbt_enhanced.py data fetch BTCUSDT 5m  - Fetch market data"
echo "  • python quantbt_enhanced.py backtest run       - Run backtest"
echo "  • python quantbt_enhanced.py optimize quick     - Quick optimization"
echo "  • python quantbt_enhanced.py monitor system     - System status"
echo ""
echo "📖 Use 'python quantbt_enhanced.py COMMAND --help' for detailed options"
echo ""
echo "🔗 Global command available as: quantbt-enhanced"
echo "   (restart shell or run: source ~/.bashrc)"
