#!/usr/bin/env python3
"""
Script to automatically fix D400 docstring errors by adding periods.
"""

import os
import re
import sys


def fix_docstring_periods(file_path: str) -> bool:
    """Fix docstring periods in a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Pattern to match docstrings that don't end with a period
        # This matches both single and multi-line docstrings
        pattern = r'(\s*"""[^"]*?)([^.\s])(\s*""")'

        def add_period(match):
            prefix = match.group(1)
            last_char = match.group(2)
            suffix = match.group(3)
            return f"{prefix}{last_char}.{suffix}"

        content = re.sub(pattern, add_period, content)

        # Also handle single quote docstrings
        pattern = r"(\s*'''[^']*?)([^.\s])(\s*''')"
        content = re.sub(pattern, add_period, content)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed: {file_path}")
            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to process files."""
    if len(sys.argv) > 1:
        target_dirs = sys.argv[1:]
    else:
        target_dirs = ['core']

    fixed_count = 0

    for target_dir in target_dirs:
        if not os.path.exists(target_dir):
            print(f"Directory {target_dir} does not exist")
            continue

        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    if fix_docstring_periods(file_path):
                        fixed_count += 1

    print(f"Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
