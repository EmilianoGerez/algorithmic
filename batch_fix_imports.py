#!/usr/bin/env python3
"""
Batch fix common flake8 import and style issues.
"""
import os
import re


def fix_file_imports(filepath):
    """Fix common import issues in a file."""
    if not os.path.exists(filepath):
        return False

    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content
    changes_made = False

    # Fix import order: move 'import logging' before other imports
    if 'core/data/adapters.py' in filepath:
        content = re.sub(
            r'from decimal import Decimal\nimport logging',
            'import logging\nfrom decimal import Decimal',
            content
        )
        if content != original_content:
            changes_made = True

    # Remove unused imports from demo_alpaca_backtest.py
    if 'demo_alpaca_backtest.py' in filepath:
        # Remove CoreBacktestEngine and RiskManager from imports
        content = re.sub(
            r'(\s+)CoreBacktestEngine,\n',
            '',
            content
        )
        content = re.sub(
            r'(\s+)RiskManager,\n',
            '',
            content
        )
        if content != original_content:
            changes_made = True

    # Save changes if any were made
    if changes_made:
        with open(filepath, 'w') as f:
            f.write(content)
        return True

    return False


def main():
    """Fix imports in key files."""
    base_dir = os.path.dirname(os.path.abspath(__file__))

    files_to_fix = [
        'core/data/adapters.py',
        'demo_alpaca_backtest.py',
    ]

    for filepath in files_to_fix:
        full_path = os.path.join(base_dir, filepath)
        if fix_file_imports(full_path):
            print(f"Fixed imports in {filepath}")
        else:
            print(f"No changes needed in {filepath}")


if __name__ == "__main__":
    main()
