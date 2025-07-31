#!/bin/bash
# Setup script for pre-commit hooks

set -e

echo "🔧 Setting up pre-commit hooks for automatic code quality checks..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found at .venv"
    echo "   Please create and activate your virtual environment first"
    exit 1
fi

# Install pre-commit if not already installed
if ! .venv/bin/pip show pre-commit > /dev/null 2>&1; then
    echo "📦 Installing pre-commit..."
    .venv/bin/pip install pre-commit
else
    echo "✅ Pre-commit already installed"
fi

# Install the hooks
echo "🪝 Installing pre-commit hooks..."
.venv/bin/pre-commit install

# Update hook repositories to latest versions
echo "🔄 Updating hook repositories..."
.venv/bin/pre-commit autoupdate

# Test hooks on all files
echo "🧪 Testing hooks on all files..."
if .venv/bin/pre-commit run --all-files; then
    echo ""
    echo "🎉 Pre-commit setup complete!"
    echo ""
    echo "What happens now:"
    echo "  • Before each commit, the following checks will run automatically:"
    echo "    - Ruff linting with auto-fix"
    echo "    - Ruff formatting"
    echo "    - MyPy type checking (strict mode)"
    echo "    - Trailing whitespace removal"
    echo "    - End-of-file fixing"
    echo "    - YAML/TOML syntax validation"
    echo "    - Merge conflict detection"
    echo "    - Large file checking"
    echo "    - Basic tests (if they exist)"
    echo ""
    echo "  • If any check fails, the commit will be blocked"
    echo "  • Auto-fixable issues will be fixed automatically"
    echo "  • You can run checks manually with: .venv/bin/pre-commit run --all-files"
    echo ""
    echo "✅ Your commits will now be automatically validated!"
else
    echo ""
    echo "⚠️  Some hooks failed, but that's expected on first run"
    echo "   The hooks have fixed issues automatically"
    echo "   Run 'git add .' and commit again to complete setup"
fi
