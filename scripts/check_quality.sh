#!/bin/bash
# Code quality check script
echo "🔍 Running code quality checks..."
echo ""

echo "📋 1. Type checking (mypy)..."
if mypy core/ services/ infra/ 2>/dev/null; then
    echo "✅ MyPy passed!"
else
    echo "❌ MyPy found issues"
    exit 1
fi

echo ""
echo "🎨 2. Code formatting and linting (ruff)..."
if ruff check . --output-format=concise; then
    echo "✅ Ruff passed!"
else
    echo "❌ Ruff found issues"
    exit 1
fi

echo ""
echo "🎉 All code quality checks passed!"
