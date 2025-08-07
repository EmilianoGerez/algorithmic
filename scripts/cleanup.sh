#!/bin/bash
"""
Project cleanup script for QuantBT.

This script removes temporary files, caches, and build artifacts.
"""

echo "🧹 Cleaning up QuantBT project..."

# Remove Python cache files
echo "🗑️  Removing Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

# Remove build artifacts
echo "🗑️  Removing build artifacts..."
rm -rf build/ dist/ *.egg-info/ 2>/dev/null || true

# Remove test artifacts
echo "🗑️  Removing test artifacts..."
rm -rf .pytest_cache/ .coverage htmlcov/ 2>/dev/null || true

# Remove IDE files
echo "🗑️  Removing IDE files..."
rm -rf .vscode/settings.json .idea/ 2>/dev/null || true

# Clean up temporary files
echo "🗑️  Removing temporary files..."
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.temp" -delete 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true

# Clean up optimization cache (keep structure)
echo "🗑️  Cleaning optimization cache..."
find cache/ -name "*.pkl" -delete 2>/dev/null || true
find cache/ -name "*.json" -delete 2>/dev/null || true

echo "✅ Cleanup complete!"
echo "📁 Project is now clean and ready for fresh runs."
