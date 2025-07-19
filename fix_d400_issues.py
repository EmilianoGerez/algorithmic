#!/usr/bin/env python3
"""
Efficiently fix D400 docstring period issues by adding periods to docstrings that are missing them.
"""
import os
import re
import subprocess


def fix_docstring_periods(content):
    """Fix docstring periods in file content."""
    # Pattern to match docstrings that don't end with periods
    # Matches: """Text that doesn't end with period"""
    pattern = r'([ ]*"""[^"]*[^.?!])"""'

    def add_period(match):
        return f"{match.group(1)}.{match.group(0)[-3:]}"

    # Apply the fix
    fixed_content = re.sub(pattern, add_period, content)
    return fixed_content


def process_file(filepath):
    """Process a single file to fix D400 issues."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        fixed_content = fix_docstring_periods(content)

        if fixed_content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def main():
    """Fix D400 issues across the project."""
    # Get files with D400 issues
    cmd = [
        'python', '-m', 'flake8', '.',
        '--select=D400',
        '--max-line-length=88',
        '--exclude=venv,__pycache__,.git,.pytest_cache,htmlcov,build,dist,tests/conftest_old.py,tests/conftest_clean.py,fix_docstrings.py,batch_fix_imports.py'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
        if result.returncode != 0:
            lines = result.stdout.strip().split('\n')
            files_with_issues = set()

            for line in lines:
                if ':' in line and 'D400' in line:
                    filepath = line.split(':')[0]
                    if filepath.startswith('./'):
                        filepath = filepath[2:]
                    files_with_issues.add(filepath)

            print(f"Found {len(files_with_issues)} files with D400 issues")

            fixed_count = 0
            for filepath in sorted(files_with_issues):
                if os.path.exists(filepath):
                    if process_file(filepath):
                        fixed_count += 1
                        print(f"Fixed: {filepath}")

            print(f"\nFixed D400 issues in {fixed_count} files")
        else:
            print("No D400 issues found")

    except Exception as e:
        print(f"Error running flake8: {e}")


if __name__ == "__main__":
    main()
