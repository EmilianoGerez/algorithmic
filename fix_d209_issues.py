#!/usr/bin/env python3
"""
Fix D209 docstring issues - multi-line docstring closing quotes should be on a separate line.
"""

import os
import re


def fix_d209_docstrings(file_path: str) -> bool:
    """Fix D209 docstring issues in a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        original_content = content

        # Pattern to match docstrings that end with content and quotes on same line
        # This matches """...content.""" and converts to """...content.\n    """
        pattern = r'("""[^"]*?)(\.""")'

        def replace_docstring(match):
            docstring_content = match.group(1)
            # Check if this is a single-line docstring (no newlines in content)
            if '\n' not in docstring_content.replace('"""', ''):
                return match.group(0)  # Don't change single-line docstrings

            # For multi-line docstrings, move closing quotes to new line
            # Determine indentation from the line
            lines = docstring_content.split('\n')
            if len(lines) > 1:
                # Get indentation from the line containing the opening quotes
                first_line = lines[0]
                indent_match = re.search(r'^(\s*)', first_line)
                indent = indent_match.group(1) if indent_match else '    '
                return f'{docstring_content}.\n{indent}"""'
            return match.group(0)

        # Apply the pattern
        content = re.sub(pattern, replace_docstring, content)

        # Also fix cases where quotes are on same line as content without period
        pattern2 = r'("""[^"]*[^.\n])"""'

        def replace_docstring2(match):
            docstring_content = match.group(1)
            # Check if this is a single-line docstring
            if '\n' not in docstring_content.replace('"""', ''):
                return match.group(0)  # Don't change single-line docstrings

            # For multi-line docstrings, move closing quotes to new line
            lines = docstring_content.split('\n')
            if len(lines) > 1:
                first_line = lines[0]
                indent_match = re.search(r'^(\s*)', first_line)
                indent = indent_match.group(1) if indent_match else '    '
                return f'{docstring_content}\n{indent}"""'
            return match.group(0)

        content = re.sub(pattern2, replace_docstring2, content)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to fix D209 issues in Python files."""
    files_to_fix = [
        "btc_backtest_config.py",
        "core/backtesting/__init__.py",
        "core/data/__init__.py",
        "core/data/adapters.py",
        "core/data/feeds.py",
        "core/data/models.py",
        "core/indicators/__init__.py",
        "core/indicators/fvg_detector.py",
        "core/indicators/technical.py",
        "core/live/__init__.py",
        "core/risk/__init__.py",
        "core/signals/__init__.py",
        "core/signals/signal_processor.py",
        "core/strategies/__init__.py",
        "core/strategies/base_strategy.py",
        "core/strategies/fvg_strategy.py",
        "core/streaming/__init__.py",
        "demo_alpaca_backtest.py",
        "demo_core_system.py",
        "demo_phase2_system.py",
        "demo_phase3_system.py",
        "setup_alpaca.py",
        "test_alpaca_integration.py",
        "test_complete_system.py",
        "test_phase3_system.py",
    ]

    fixed_count = 0

    for file_path in files_to_fix:
        if os.path.exists(file_path):
            if fix_d209_docstrings(file_path):
                print(f"✅ Fixed D209 issues in {file_path}")
                fixed_count += 1
            else:
                print(f"📄 No D209 issues found in {file_path}")
        else:
            print(f"⚠️  File not found: {file_path}")

    print(f"\n🎉 Fixed D209 issues in {fixed_count} files")


if __name__ == "__main__":
    main()
