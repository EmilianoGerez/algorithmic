#!/usr/bin/env python3
"""Debug pool creation timing in detail."""

from datetime import UTC, datetime

import yaml

from core.strategy.factory import StrategyFactory
from services.models import BacktestConfig


def debug_pool_creation():
    """Debug pool creation timing step by step."""
    print("=== Pool Creation Timing Debug ===")

    # Load config and build strategy
    with open("configs/binance.yaml") as f:
        config_dict = yaml.safe_load(f)
    config = BacktestConfig(**config_dict)
    strategy = StrategyFactory.build(config)

    # Get components
    htf = strategy.htf_stack
    pool_manager = htf.pool_manager
    pool_registry = htf.pool_registry
    ttl_wheel = pool_registry._ttl_wheel

    print(f"Initial TTL wheel time: {ttl_wheel.current_time}")

    # Simulate advancing to May 19, 16:00 (when the May 19 bullish FVG occurs)
    may19_time = datetime(2025, 5, 19, 16, 0, 0, tzinfo=UTC)
    print(f"Advancing TTL wheel to: {may19_time}")

    # Advance TTL wheel properly
    try:
        expired = ttl_wheel.tick(may19_time)
        print(f"✅ TTL wheel advanced successfully, expired items: {len(expired)}")
        print(f"TTL wheel current time now: {ttl_wheel.current_time}")
    except Exception as e:
        print(f"❌ TTL wheel advancement failed: {e}")
        return

    # Now try to create a pool manually
    timeframe = "240"
    strength = 0.534
    ttl = pool_manager.config.get_ttl_for_timeframe(timeframe)

    print("Attempting to create pool:")
    print(f"  Timeframe: {timeframe}")
    print(f"  Created at: {may19_time}")
    print(f"  TTL: {ttl}")
    print(f"  Expires at: {may19_time + ttl}")
    print(f"  TTL wheel current time: {ttl_wheel.current_time}")

    # Manually call pool creation
    success, pool_id = pool_registry.create_pool(
        timeframe=timeframe,
        top=105519.80,
        bottom=103359.50,
        strength=strength,
        created_at=may19_time,
    )

    print(f"Pool creation result: success={success}, pool_id={pool_id}")

    if success:
        print("✅ Pool created successfully!")
        print(f"Registry now has {len(pool_registry._pools)} pools")
    else:
        print("❌ Pool creation failed")

        # Debug why it failed
        print("Debugging failure...")

        # Check if it's a duplicate
        test_id = f"240_{may19_time.isoformat()}_{hash('test') & 0xFFFFFFFF:08x}"
        if test_id in pool_registry._pools:
            print(f"  - Duplicate pool ID: {test_id}")

        # Check TTL scheduling manually
        expires_at = may19_time + ttl
        manual_schedule = ttl_wheel.schedule(
            f"manual_test_{may19_time.timestamp()}", expires_at, may19_time
        )
        print(f"  - Manual TTL schedule test: {manual_schedule}")

        if not manual_schedule:
            print(
                f"    - expires_at <= current_time? {expires_at <= ttl_wheel.current_time}"
            )
            print(f"    - expires_at: {expires_at}")
            print(f"    - current_time: {ttl_wheel.current_time}")


if __name__ == "__main__":
    debug_pool_creation()
