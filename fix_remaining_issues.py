#!/usr/bin/env python3
"""Final automated fixes for remaining flake8 violations."""

import os
import re
import subprocess

def fix_whitespace_around_operators(file_path):
    """Fix E226 - missing whitespace around arithmetic operators."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix missing spaces around arithmetic operators
    patterns = [
        (r'(\w)(\*)(\w)', r'\1 \2 \3'),  # word*word -> word * word
        (r'(\w)(\+)(\w)', r'\1 \2 \3'),  # word+word -> word + word  
        (r'(\w)(-)(\w)', r'\1 \2 \3'),   # word-word -> word - word
        (r'(\w)(/)(\w)', r'\1 \2 \3'),   # word/word -> word / word
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    
    with open(file_path, 'w') as f:
        f.write(content)

def fix_unused_variables(file_path):
    """Fix F841 - prefix unused variables with underscore."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find variables that are assigned but never used
    unused_vars = []
    
    # Run flake8 to find F841 violations
    result = subprocess.run(
        ['python', '-m', 'flake8', '--select=F841', file_path],
        capture_output=True, text=True
    )
    
    for line in result.stdout.split('\n'):
        if 'F841' in line and 'local variable' in line:
            # Extract variable name from error message
            match = re.search(r"local variable '(\w+)' is assigned", line)
            if match:
                var_name = match.group(1)
                if not var_name.startswith('_'):
                    unused_vars.append(var_name)
    
    # Replace variable assignments
    for i, line in enumerate(lines):
        for var in unused_vars:
            # Match assignment patterns
            pattern = rf'(\s+)({var})(\s*=)'
            if re.search(pattern, line):
                lines[i] = re.sub(pattern, rf'\1_{var}\3', line)
    
    if unused_vars:
        with open(file_path, 'w') as f:
            f.writelines(lines)
        print(f"Fixed unused variables in {file_path}: {unused_vars}")

def fix_line_length_issues():
    """Fix E501 - line too long issues in key files."""
    long_line_fixes = {
        './demo_phase2_system.py': [
            (255, 'streaming_config.update({\n            "realtime_processing": True\n        })')
        ],
        './demo_phase3_system.py': [
            (238, 'print(f"Paper trading position for {symbol}: "\n              f"{position.quantity} @ ${position.avg_price:.2f}")'),
            (294, 'print(f"Live trading - Total P&L: "\n              f"${total_pnl:.2f}")'),
            (322, 'print(f"Risk analysis - Position size: "\n              f"{position_size} shares")'),
            (336, 'print(f"Streaming - Received {len(market_data)} "\n              f"data points for {symbol}")'),
            (384, 'print(f"Strategy validation - FVG count: "\n              f"{fvg_count}")'),
            (396, 'print(f"Performance metrics - Sharpe ratio: "\n              f"{sharpe_ratio:.3f}")')
        ]
    }
    
    for file_path, fixes in long_line_fixes.items():
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            for line_num, replacement in fixes:
                if line_num <= len(lines):
                    # Find the line and replace it
                    original_indent = len(lines[line_num-1]) - len(lines[line_num-1].lstrip())
                    indent = ' ' * original_indent
                    lines[line_num-1] = f'{indent}{replacement}\n'
            
            with open(file_path, 'w') as f:
                f.writelines(lines)
            print(f"Fixed line length issues in {file_path}")

def main():
    """Run all automated fixes."""
    print("🔧 Running final automated fixes...")
    
    # Get all Python files in the project (excluding venv)
    python_files = []
    for root, dirs, files in os.walk('.'):
        # Skip virtual environment directories
        dirs[:] = [d for d in dirs if d not in ['venv', '.venv', 'env', '__pycache__']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    # Fix whitespace around operators
    print("Fixing whitespace around arithmetic operators...")
    files_with_e226 = [
        './demo_core_system.py',
        './demo_phase3_system.py', 
        './test_alpaca_integration.py',
        './test_runner.py'
    ]
    
    for file_path in files_with_e226:
        if os.path.exists(file_path):
            fix_whitespace_around_operators(file_path)
            print(f"Fixed whitespace in {file_path}")
    
    # Fix unused variables
    print("Fixing unused variables...")
    files_with_f841 = [
        './demo_alpaca_backtest.py',
        './demo_phase2_system.py',
        './demo_phase3_system.py',
        './test_alpaca_integration.py',
        './test_complete_system.py',
        './test_phase3_system.py'
    ]
    
    for file_path in files_with_f841:
        if os.path.exists(file_path):
            fix_unused_variables(file_path)
    
    # Fix line length issues
    print("Fixing line length issues...")
    fix_line_length_issues()
    
    print("✅ Automated fixes completed!")
    print("\nRunning flake8 to check remaining violations...")
    
    # Run flake8 to see the improvement
    result = subprocess.run(
        ['python', '-m', 'flake8', '--exclude=venv,./venv,.venv,env', 
         '--count', '--select=E,W,F,C,I', '.'],
        capture_output=True, text=True
    )
    
    violations = result.stdout.strip().split('\n')[-1] if result.stdout else "0"
    print(f"Remaining violations: {violations}")

if __name__ == "__main__":
    main()
