#!/usr/bin/env python3
"""Quick script to fix the most common D400 issues."""

# Files and their first line docstring fixes
files_to_fix = {
    'btc_backtest_config.py': ('Bitcoin Backtesting Configuration', 'Bitcoin Backtesting Configuration.'),
    'demo_core_system.py': ('Demo: Core System Components', 'Demo: Core System Components.'),
    'demo_alpaca_backtest.py': ('Advanced Alpaca Integration Demo', 'Advanced Alpaca Integration Demo.'),
    'demo_phase2_system.py': ('Phase 2: Complete System Integration Demo', 'Phase 2: Complete System Integration Demo.'),
    'demo_phase3_system.py': ('Phase 3: Live Trading & Real-time System Demo', 'Phase 3: Live Trading & Real-time System Demo.'),
    'setup_alpaca.py': ('Interactive Alpaca Broker Setup Script', 'Interactive Alpaca Broker Setup Script.'),
    'test_alpaca_integration.py': ('Test Alpaca Integration', 'Test Alpaca Integration.'),
    'test_complete_system.py': ('Comprehensive System Integration Test Suite', 'Comprehensive System Integration Test Suite.'),
    'test_phase3_system.py': ('Phase 3 System Integration Tests', 'Phase 3 System Integration Tests.'),
}

for file_path, (old_text, new_text) in files_to_fix.items():
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the first line
        content = content.replace(old_text, new_text, 1)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Fixed D400 in {file_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

print("D400 fixes completed")
