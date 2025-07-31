"""
Unit test for factory pool manager integration fix.

Tests that PoolManager integration works with the StrategyFactory.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.detectors.fvg import FVGEvent
from services.metrics import MetricsCollector
from services.models import BacktestConfig


class TestFactoryPoolManagerIntegration:
    """Test the factory pool manager integration fix."""

    def test_pool_manager_integration_via_factory(self):
        """Test that pool manager integration works via factory initialization."""

        # Skip if no data file exists (for CI)
        if not Path("data/BTCUSDT_5m_2025-05-18_futures.csv").exists():
            pytest.skip("Data file not available in CI environment")

        # Use original config file approach for local testing
        import yaml

        with open("configs/binance.yaml") as f:
            config_data = yaml.safe_load(f)

        config = BacktestConfig.model_validate(config_data)

        # Test strategy factory directly
        from core.strategy.factory import StrategyFactory

        # Initialize metrics collector
        metrics_collector = MetricsCollector()

        # Test strategy creation via factory
        strategy = StrategyFactory.build(
            config=config, metrics_collector=metrics_collector
        )

        # Verify pool manager exists and has the required method
        assert hasattr(strategy, "pool_manager"), (
            "Strategy should have pool_manager attribute"
        )
        assert strategy.pool_manager is not None, "Pool manager should not be None"
        assert hasattr(strategy.pool_manager, "process_detector_event"), (
            "Pool manager should have process_detector_event method"
        )

        print("✅ Pool manager integration verified successfully")
        print(f"✅ Strategy has pool_manager: {hasattr(strategy, 'pool_manager')}")
        print(
            f"✅ Pool manager process_detector_event callable: {hasattr(strategy.pool_manager, 'process_detector_event')}"
        )


if __name__ == "__main__":
    test = TestFactoryPoolManagerIntegration()
    try:
        test.test_pool_manager_integration_via_factory()
        print("✅ Factory pool manager integration test passed!")
    except pytest.skip.Exception:
        print("⏭️ Skipped factory test (no data file - this is expected in CI)")
