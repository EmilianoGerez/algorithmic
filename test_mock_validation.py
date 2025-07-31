#!/usr/bin/env python3
"""
Final integration test for the refactor.
Tests that the mock component validation works as expected.
"""

import sys
from pathlib import Path

import yaml

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.strategy.factory import StrategyFactory  # noqa: E402


def test_mock_validation():
    """Test that mock component validation works."""
    print("=== Testing Mock Component Validation ===")

    # Load the binance config
    config_path = project_root / "configs" / "binance.yaml"
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    # Convert to object with attributes
    class ConfigObj:
        def __init__(self, data):
            for key, value in data.items():
                if isinstance(value, dict):
                    setattr(self, key, ConfigObj(value))
                else:
                    setattr(self, key, value)

    config = ConfigObj(config_data)

    # Test 1: Mock components disabled should raise error
    print("Test 1: Mock components disabled, should raise error")
    try:
        strategy = StrategyFactory.build(config)
        print("❌ Expected ValueError but build succeeded")
        return False
    except ValueError as e:
        print(f"✅ Correctly raised ValueError: {e}")

    # Test 2: Enable mock components
    print("\nTest 2: Enabling mock components")
    config.runtime.use_mock_components = True

    try:
        strategy = StrategyFactory.build(config)
        print("✅ Successfully built strategy with mocks enabled")
        print(f"✅ Strategy symbol: {strategy.config.strategy.symbol}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

    return True


if __name__ == "__main__":
    try:
        success = test_mock_validation()

        if success:
            print("\n🎉 Mock validation test passed!")
            sys.exit(0)
        else:
            print("\n❌ Mock validation test failed!")
            sys.exit(1)

    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
