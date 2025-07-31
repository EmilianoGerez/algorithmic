#!/usr/bin/env python3
"""Debug configuration loading to find the type issue."""

import sys

sys.path.append("/Users/emilianogerez/Projects/python/algorithmic")

import os

from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

# Load the config the same way the backtest does
config_dir = "/Users/emilianogerez/Projects/python/algorithmic/configs"
with initialize_config_dir(config_dir=config_dir, version_base=None):
    cfg = compose(config_name="binance.yaml")

print("=== Configuration Debug ===")
print(f"Type of cfg: {type(cfg)}")
print(f"Has pools: {hasattr(cfg, 'pools')}")

if hasattr(cfg, "pools"):
    pools = cfg.pools
    print(f"Type of pools: {type(pools)}")
    print(f"Pools content: {pools}")

    if hasattr(pools, "strength_threshold"):
        st = pools.strength_threshold
        print(f"strength_threshold value: {st}")
        print(f"strength_threshold type: {type(st)}")
        print(f"Is it a string? {isinstance(st, str)}")
        print(f"Is it a number? {isinstance(st, int | float)}")

        # Try to convert
        try:
            converted = float(st)
            print(f"Converted to float: {converted} (type: {type(converted)})")
        except Exception as e:
            print(f"Failed to convert: {e}")
    else:
        print("No strength_threshold in pools")

    # Check all pool items
    print("\n=== All pools items ===")
    for key in pools:
        value = pools[key]
        print(f"{key}: {value} (type: {type(value)})")

print("\n=== Direct getattr test ===")
pools_config = getattr(cfg, "pools", {})
print(f"pools_config: {pools_config}")
strength_threshold = pools_config.get("strength_threshold", 0.1)
print(
    f"strength_threshold from get(): {strength_threshold} (type: {type(strength_threshold)})"
)
