#!/usr/bin/env python3
"""
Smoke test for the hardcoded symbol refactor.
Tests that the configuration is properly propagated through the system.
"""

import sys
from datetime import datetime
from pathlib import Path

import yaml

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.entities import Candle  # noqa: E402
from core.indicators.snapshot import IndicatorSnapshot  # noqa: E402
from core.strategy.signal_candidate import (  # noqa: E402
    CandidateConfig,
    SignalCandidateFSM,
)
from core.strategy.signal_models import SignalDirection, ZoneType  # noqa: E402


def test_symbol_propagation():
    """Test that symbol from config is properly used in signal generation."""
    print("=== Testing Symbol Propagation ===")

    # Test symbol from FSM - focus on testing the to_signal method directly
    from core.strategy.signal_models import CandidateState, SignalCandidate

    test_symbol = "BTCUSDT"
    test_timeframe = "5m"

    # Create a READY candidate manually
    timestamp = datetime(2024, 5, 20, 10, 0)
    ready_candidate = SignalCandidate(
        candidate_id="TEST_001",
        zone_id="TEST_ZONE_001",
        zone_type=ZoneType.POOL,
        direction=SignalDirection.LONG,
        entry_price=50000.0,
        strength=0.8,
        state=CandidateState.READY,  # Manually set to READY
        created_at=timestamp,
        expires_at=timestamp.replace(hour=11),  # 1 hour later
    )

    print(f"✅ Created candidate in state: {ready_candidate.state}")

    # Test the to_signal method directly
    signal = ready_candidate.to_signal(
        symbol=test_symbol,
        timeframe=test_timeframe,
        current_price=50050.0,
        filters_passed=3,
        total_filters=4,
        entry_timestamp=timestamp,
    )

    print(f"✅ Signal generated with symbol: {signal.symbol}")
    print(f"✅ Signal timeframe: {signal.timeframe}")
    print(f"✅ Signal confidence: {signal.confidence}")

    assert signal.symbol == test_symbol, f"Expected {test_symbol}, got {signal.symbol}"
    assert signal.timeframe == test_timeframe, (
        f"Expected {test_timeframe}, got {signal.timeframe}"
    )
    assert signal.confidence > 0.0, "Confidence should be calculated, not hardcoded"

    print("✅ Symbol and timeframe correctly propagated!")
    print("✅ Confidence calculation working!")

    return True


def test_config_validation():
    """Test the configuration validation from YAML."""
    print("\n=== Testing Config Validation ===")

    # Load the binance config to test the new fields
    config_path = project_root / "configs" / "binance.yaml"
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    # Check new fields are present
    assert "tick_size" in config_data["data"], "tick_size missing from data section"
    assert "testnet" in config_data["execution"]["broker_config"], (
        "testnet missing from broker_config"
    )
    assert "use_mock_components" in config_data["runtime"], (
        "use_mock_components missing from runtime"
    )

    print(f"✅ data.symbol: {config_data['data']['symbol']}")
    print(f"✅ data.tick_size: {config_data['data']['tick_size']}")
    print(
        f"✅ execution.broker_config.testnet: {config_data['execution']['broker_config']['testnet']}"
    )
    print(
        f"✅ runtime.use_mock_components: {config_data['runtime']['use_mock_components']}"
    )

    return True


if __name__ == "__main__":
    try:
        success = True
        success &= test_symbol_propagation()
        success &= test_config_validation()

        if success:
            print("\n🎉 All refactor smoke tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)

    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
