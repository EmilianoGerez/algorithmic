#!/usr/bin/env python3
"""Debug the TTL scheduling timing issue."""

from datetime import UTC, datetime

import yaml

from core.strategy.factory import StrategyFactory
from services.models import BacktestConfig


def debug_ttl_timing():
    """Debug the TTL timing issue in detail."""
    print("=== TTL Timing Debug ===")

    # Load config
    with open("configs/binance.yaml") as f:
        config_dict = yaml.safe_load(f)
    config = BacktestConfig(**config_dict)

    # Build strategy
    strategy = StrategyFactory.build(config)

    # Get references to components
    htf = strategy.htf_stack
    pool_manager = htf.pool_manager
    pool_registry = htf.pool_registry
    ttl_wheel = pool_registry._ttl_wheel

    print(f"Pool manager TTL config: {pool_manager.config.ttl_by_timeframe}")
    print(f"TTL wheel current time: {ttl_wheel.current_time}")

    # Simulate creating a pool with the May 19 16:00 FVG timing
    fvg_timestamp = datetime(2025, 5, 19, 16, 0, 0, tzinfo=UTC)
    timeframe = "240"

    # Get TTL for this timeframe
    ttl = pool_manager.config.get_ttl_for_timeframe(timeframe)
    print(f"TTL for {timeframe}: {ttl}")

    # Calculate expiry
    expires_at = fvg_timestamp + ttl
    print(f"FVG created at: {fvg_timestamp}")
    print(f"Would expire at: {expires_at}")
    print(f"TTL wheel current time: {ttl_wheel.current_time}")
    print(f"Is expires_at > current_time? {expires_at > ttl_wheel.current_time}")

    # Try manual TTL scheduling
    pool_id = "test_pool_240_may19"
    success = ttl_wheel.schedule(pool_id, expires_at, fvg_timestamp)
    print(f"Manual TTL schedule result: {success}")

    if not success:
        print("❌ TTL scheduling failed!")
        print("Possible causes:")
        print(f"  - expires_at <= current_time? {expires_at <= ttl_wheel.current_time}")
        print(f"  - pool already scheduled? {pool_id in ttl_wheel._pool_to_expiry}")
    else:
        print("✅ TTL scheduling succeeded!")


if __name__ == "__main__":
    debug_ttl_timing()
