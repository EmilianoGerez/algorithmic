#!/usr/bin/env python3
"""
Final integration test for the refactor.
Tests that the mock component validation works as expected.
"""

import sys
from pathlib import Path

import yaml

# Add the project root to the path
project_root = Path(
    __file__
).parent.parent  # Go up one level from tests/ to project root
sys.path.insert(0, str(project_root))

from core.strategy.factory import StrategyFactory  # noqa: E402


def test_mock_validation():
    """Test that mock component validation works."""
    print("=== Testing Mock Component Validation ===")

    # Load the binance config
    config_path = project_root / "configs" / "binance.yaml"
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    # Convert to object with attributes that supports dict-like access
    class ConfigObj:
        def __init__(self, data):
            self._data = data
            for key, value in data.items():
                if isinstance(value, dict):
                    setattr(self, key, ConfigObj(value))
                else:
                    setattr(self, key, value)

        def get(self, key, default=None):
            # Check if it's an attribute first (for modified values)
            if hasattr(self, key):
                return getattr(self, key)
            # Fall back to original data
            return self._data.get(key, default)

        def __getitem__(self, key):
            # Check if it's an attribute first (for modified values)
            if hasattr(self, key):
                return getattr(self, key)
            return self._data[key]

        def __contains__(self, key):
            return hasattr(self, key) or key in self._data

        def items(self):
            # Return current attribute values, not just original data
            result = {}
            for key in self._data:
                if hasattr(self, key):
                    result[key] = getattr(self, key)
                else:
                    result[key] = self._data[key]
            return result.items()

        def keys(self):
            return self._data.keys()

        def values(self):
            # Return current attribute values
            result = []
            for key in self._data:
                if hasattr(self, key):
                    result.append(getattr(self, key))
                else:
                    result.append(self._data[key])
            return result

    config = ConfigObj(config_data)

    # Test 1: Mock components disabled should raise error
    print("Test 1: Mock components disabled, should raise error")
    config.runtime.use_mock_components = False

    try:
        strategy = StrategyFactory.build(config)
        print("❌ Expected ValueError but build succeeded")
        raise AssertionError("Expected ValueError but build succeeded")
    except ValueError as e:
        print(f"✅ Correctly raised ValueError: {e}")
        assert "runtime.use_mock_components is False" in str(
            e
        )  # Test 2: Enable mock components
    print("\nTest 2: Enabling mock components")
    config.runtime.use_mock_components = True

    try:
        strategy = StrategyFactory.build(config)
        print("✅ Successfully built strategy with mocks enabled")
        print(f"✅ Strategy symbol: {strategy.config.strategy.symbol}")
        assert strategy is not None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise AssertionError(f"Unexpected error: {e}") from e

    print("✅ All mock validation tests passed!")


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
