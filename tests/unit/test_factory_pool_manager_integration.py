"""
Unit test for factory pool manager integration fix.

Tests that PoolManager.process_detector_event is called during HTF strategy execution.
"""

from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime
from core.entities import Candle
from core.detectors.fvg import FVGEvent
from services.runner import BacktestRunner
from services.models import BacktestConfig
import yaml


class TestFactoryPoolManagerIntegration:
    """Test the factory pool manager integration fix."""
    
    def test_pool_manager_integration_via_backtest(self):
        """Test that pool manager integration works via full backtest."""
        
        # Load actual config
        with open('configs/binance.yaml', 'r') as f:
            config_data = yaml.safe_load(f)
        
        config = BacktestConfig.model_validate(config_data)
        runner = BacktestRunner(config)
        
        # Patch the pool manager to track calls
        original_process_event = None
        process_event_spy = MagicMock()
        
        def setup_spy():
            nonlocal original_process_event
            if hasattr(runner, 'strategy') and hasattr(runner.strategy, 'pool_manager'):
                original_process_event = runner.strategy.pool_manager.process_detector_event
                def spy_wrapper(*args, **kwargs):
                    process_event_spy(*args, **kwargs)
                    return original_process_event(*args, **kwargs)
                runner.strategy.pool_manager.process_detector_event = spy_wrapper
        
        # Monkey patch the strategy creation to inject our spy
        original_build_strategy = runner._build_strategy
        def patched_build_strategy():
            result = original_build_strategy()
            setup_spy()
            return result
        runner._build_strategy = patched_build_strategy
        
        # Run backtest
        result = runner.run()
        
        # Verify that process_detector_event was called
        assert process_event_spy.call_count > 0, (
            "PoolManager.process_detector_event should be called during backtest. "
            "This verifies the factory patch is working correctly."
        )
        
        print(f"✅ Pool manager process_detector_event called {process_event_spy.call_count} times")
        print(f"✅ Backtest completed with {len(result.trades)} trades")


if __name__ == "__main__":
    test = TestFactoryPoolManagerIntegration()
    test.test_pool_manager_integration_via_backtest()
    print("✅ Factory pool manager integration test passed!")
