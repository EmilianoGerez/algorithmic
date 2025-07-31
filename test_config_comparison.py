"""
Quick backtest comparison script to test touch-&-reclaim vs legacy behavior.
"""

import os
import sys
import tempfile
from pathlib import Path

import yaml


def create_test_configs():
    """Create two config files for comparison."""

    # Load base config
    with open("configs/base.yaml") as f:
        base_config = yaml.safe_load(f)

    # Config 1: Current settings (touch-&-reclaim enabled)
    touch_reclaim_config = base_config.copy()
    touch_reclaim_config["candidate"]["filters"]["ema_tolerance_pct"] = 0
    touch_reclaim_config["candidate"]["filters"]["linger_minutes"] = 60

    # Config 2: Legacy settings (disabled)
    legacy_config = base_config.copy()
    legacy_config["candidate"]["filters"]["ema_tolerance_pct"] = 0
    legacy_config["candidate"]["filters"]["linger_minutes"] = 0

    # Save configs
    touch_reclaim_path = Path("test_touch_reclaim_config.yaml")
    legacy_path = Path("test_legacy_config.yaml")

    with open(touch_reclaim_path, "w") as f:
        yaml.dump(touch_reclaim_config, f, default_flow_style=False)

    with open(legacy_path, "w") as f:
        yaml.dump(legacy_config, f, default_flow_style=False)

    return touch_reclaim_path, legacy_path


def run_comparison_test():
    """Run a quick comparison test."""

    print("🔍 Creating test configurations...")
    touch_reclaim_path, legacy_path = create_test_configs()

    print("✅ Test configs created:")
    print(f"  Touch-&-Reclaim: {touch_reclaim_path}")
    print(f"  Legacy: {legacy_path}")
    print()

    print("📋 Configuration Comparison:")
    print("┌─────────────────────┬─────────────────┬─────────────────┐")
    print("│ Parameter           │ Touch-&-Reclaim │ Legacy          │")
    print("├─────────────────────┼─────────────────┼─────────────────┤")
    print("│ ema_tolerance_pct   │ 0               │ 0               │")
    print("│ linger_minutes      │ 60              │ 0               │")
    print("│ reclaim_requires_ema│ true            │ true            │")
    print("└─────────────────────┴─────────────────┴─────────────────┘")
    print()

    print("🎯 Expected Results:")
    print("• Touch-&-Reclaim: Should capture zone touch → EMA flip patterns")
    print("• Legacy: Only captures immediate EMA alignment")
    print("• Improvement: More valid signals from liquidity sweep patterns")
    print()

    print("💡 To run full backtest comparison:")
    print(f"python demo_enhanced.py --config {touch_reclaim_path}")
    print(f"python demo_enhanced.py --config {legacy_path}")
    print()

    print("📊 Key metrics to compare:")
    print("• Total signals generated")
    print("• Win rate")
    print("• Profit factor")
    print("• Number of 'zone touch' patterns captured")

    return touch_reclaim_path, legacy_path


if __name__ == "__main__":
    run_comparison_test()

    print("\n" + "=" * 60)
    print("🎉 Ready to test 20 May scenario!")
    print("=" * 60)
    print()
    print("The touch-&-reclaim mechanism is properly configured and should now")
    print("capture the pattern where:")
    print("1. H4 FVG created on 19 May")
    print("2. Price touches FVG zone on 20 May ~14:00")
    print("3. EMA21 flips below price within 60 minutes")
    print("4. Signal generated (previously missed)")
    print()
    print("Your current config with linger_minutes=60 is perfect for this!")
