#!/usr/bin/env python3
"""Test that entry spacing configuration is properly loaded in StrategyFactory."""

import yaml

from core.strategy.factory import StrategyFactory
from services.models import BacktestConfig


def test_entry_spacing_config():
    """Test that entry spacing configuration is properly loaded."""
    print("=== Testing Entry Spacing Configuration ===")

    # Load the actual config
    with open("configs/binance.yaml") as f:
        config_dict = yaml.safe_load(f)

    # Convert to BacktestConfig
    config = BacktestConfig(**config_dict)

    print(f"Loaded config: {config.strategy.name}")
    print(f"Candidate config: {getattr(config, 'candidate', 'NOT_FOUND')}")

    # Build strategy
    strategy = StrategyFactory.build(config)

    # Check if ZoneWatcher has correct configuration
    if (
        hasattr(strategy, "htf_stack")
        and strategy.htf_stack
        and strategy.htf_stack.zone_watcher
    ):
        zone_watcher = strategy.htf_stack.zone_watcher
        zone_config = zone_watcher.config

        print("\n=== ZoneWatcher Configuration ===")
        print(f"min_entry_spacing_minutes: {zone_config.min_entry_spacing_minutes}")
        print(f"global_min_entry_spacing: {zone_config.global_min_entry_spacing}")
        print(f"enable_spacing_throttle: {zone_config.enable_spacing_throttle}")

        # Verify values match config
        expected_spacing = config.candidate.get("min_entry_spacing_minutes", 30)
        expected_global = config.candidate.get("global_min_entry_spacing", 10)
        expected_enabled = config.candidate.get("enable_spacing_throttle", True)

        print("\n=== Verification ===")
        print(
            f"min_entry_spacing_minutes: {zone_config.min_entry_spacing_minutes} == {expected_spacing} ✓"
            if zone_config.min_entry_spacing_minutes == expected_spacing
            else f"❌ {zone_config.min_entry_spacing_minutes} != {expected_spacing}"
        )
        print(
            f"global_min_entry_spacing: {zone_config.global_min_entry_spacing} == {expected_global} ✓"
            if zone_config.global_min_entry_spacing == expected_global
            else f"❌ {zone_config.global_min_entry_spacing} != {expected_global}"
        )
        print(
            f"enable_spacing_throttle: {zone_config.enable_spacing_throttle} == {expected_enabled} ✓"
            if zone_config.enable_spacing_throttle == expected_enabled
            else f"❌ {zone_config.enable_spacing_throttle} != {expected_enabled}"
        )

    else:
        print("❌ No HTF ZoneWatcher found in strategy")


if __name__ == "__main__":
    test_entry_spacing_config()
