#!/bin/bash

# Quantbt Setup Script
# This script sets up the quantbt command for easy access

echo "🚀 Setting up Quantbt CLI..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the algorithmic project root directory"
    exit 1
fi

# Install the package in development mode if not already installed
echo "📦 Installing package in development mode..."
.venv/bin/pip install -e . --quiet

# Check if quantbt command exists in venv
if [ ! -f ".venv/bin/quantbt" ]; then
    echo "❌ Error: quantbt command not found in virtual environment"
    exit 1
fi

# Add alias to shell configuration
SHELL_CONFIG=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_CONFIG="$HOME/.bash_profile"
fi

if [ ! -z "$SHELL_CONFIG" ]; then
    # Check if alias already exists
    if ! grep -q "alias quantbt=" "$SHELL_CONFIG"; then
        echo "🔧 Adding quantbt alias to $SHELL_CONFIG..."
        echo "" >> "$SHELL_CONFIG"
        echo "# Quantbt CLI alias" >> "$SHELL_CONFIG"
        echo "alias quantbt='$(pwd)/.venv/bin/quantbt'" >> "$SHELL_CONFIG"
        echo "✅ Alias added to $SHELL_CONFIG"
    else
        echo "✅ Quantbt alias already exists in $SHELL_CONFIG"
    fi
fi

echo "🎯 Testing quantbt command..."
.venv/bin/quantbt --help > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Quantbt command is working!"
else
    echo "❌ Error: quantbt command test failed"
    exit 1
fi

echo ""
echo "🎉 Setup complete! You can now use quantbt in the following ways:"
echo ""
echo "1. Direct path (always works):"
echo "   .venv/bin/quantbt run data/BTC_USD_5min_20250727_231139.csv --config configs/base.yaml --plot"
echo ""
echo "2. After reloading your shell (source ~/.zshrc or restart terminal):"
echo "   quantbt run data/BTC_USD_5min_20250727_231139.csv --config configs/base.yaml --plot"
echo ""
echo "📖 Available commands:"
echo "   quantbt run      - Execute backtest"
echo "   quantbt multirun - Parameter optimization"
echo "   quantbt validate - Validate configuration"
echo ""
echo "📁 Data files available:"
ls -la data/ | grep -E "\.(csv|parquet)$" | awk '{print "   " $9}'
echo ""
echo "⚡ Example commands:"
echo "   quantbt run data/BTC_USD_5min_20250727_231139.csv --config configs/base.yaml --plot"
echo "   quantbt run data/BTC_USD_5min_20250727_231139.csv --config configs/base.yaml --walk 3"
echo "   quantbt run --help"
