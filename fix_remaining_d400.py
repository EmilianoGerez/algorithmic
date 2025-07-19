#!/usr/bin/env python3
"""
Fix remaining D400 docstring issues.
"""

import os
import subprocess


def fix_d400_issues():
    """Fix D400 docstring issues by adding periods."""
    # Get D400 violations
    result = subprocess.run(
        ["python", "-m", "flake8", ".", "--select=D400", "--format=%(path)s:%(row)d:%(col)d: %(text)s"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("No D400 violations found or flake8 error")
        return

    violations = []
    for line in result.stdout.strip().split('\n'):
        if line and 'D400' in line:
            parts = line.split(':', 3)
            if len(parts) >= 3:
                file_path = parts[0]
                line_num = int(parts[1])
                violations.append((file_path, line_num))

    files_to_fix = {}
    for file_path, line_num in violations:
        if file_path not in files_to_fix:
            files_to_fix[file_path] = []
        files_to_fix[file_path].append(line_num)

    for file_path, line_numbers in files_to_fix.items():
        if not os.path.exists(file_path):
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Sort line numbers in reverse order to avoid index shifting
            for line_num in sorted(line_numbers, reverse=True):
                if line_num <= len(lines):
                    line_idx = line_num - 1
                    line = lines[line_idx]

                    # Check if this is a docstring line that ends with quotes
                    if ('"""' in line or "'''" in line) and not line.rstrip().endswith('.'):
                        # Add period before closing quotes
                        if line.rstrip().endswith('"""'):
                            lines[line_idx] = line.rstrip()[:-3] + '."""\n'
                        elif line.rstrip().endswith("'''"):
                            lines[line_idx] = line.rstrip()[:-3] + ".'''\n"

                        print(f"Fixed D400 in {file_path}:{line_num}")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print("D400 fixes completed")


if __name__ == "__main__":
    fix_d400_issues()
