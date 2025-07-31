#!/bin/bash
# Clean mypy check for core modules only
echo "🔍 Running mypy on core modules..."
mypy core/ services/ infra/ 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Core modules are mypy-clean!"
else
    echo "❌ Found mypy issues in core modules"
    exit 1
fi
