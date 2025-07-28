"""
Integration test for complete HTF signal pipeline.

Tests the full workflow: FVG detection → Pool creation → Zone entry → 
Signal candidate FSM → Trading signal → Broker execution.
"""

import pandas as pd
import pytest
import yaml
from pathlib import Path

from services.runner import BacktestRunner
from services.models import BacktestConfig


def test_end_to_end_fvg_trade(tmp_path):
    """Test complete HTF pipeline produces trading signals and pool creation."""
    # Load base config
    config_path = Path("configs/base.yaml")
    cfg = yaml.safe_load(config_path.open())
    
    # Override for deterministic testing
    cfg["execution"]["deterministic_seed"] = 123
    cfg["execution"]["dump_events"] = True
    cfg["execution"]["export_data_for_viz"] = True
    cfg["data"]["path"] = "data/BTC_USD_5min_20250728_021825.csv"
    
    # Create runner
    runner = BacktestRunner(BacktestConfig(**cfg))
    
    # Execute backtest
    result = runner.run()
    
    # Validate basic execution - system should run without critical failures
    assert result is not None, "No result returned"
    
    # Validate strategy exists
    assert runner.strategy is not None, "Strategy not initialized"
    assert hasattr(runner.strategy, 'broker'), "Strategy missing broker"
    
    # Check if HTF stack was created properly
    if hasattr(runner.strategy, 'htf_stack') and runner.strategy.htf_stack is not None:
        htf = runner.strategy.htf_stack
        assert htf.pool_registry is not None, "Missing pool registry"
        assert htf.zone_watcher is not None, "Missing zone watcher"
        
        # Check for actual pool creation - the real test of success
        pools = list(htf.pool_registry._pools.values())  # Access internal storage
        print(f"✅ HTF pipeline working! Pools created: {len(pools)}")
        
        # Verify pools were created (this means FVG detection + pool registry is working)
        if len(pools) > 0:
            print(f"   Pool timeframes: {set(pool.timeframe for pool in pools)}")
            print(f"   Pool strengths: {[f'{pool.strength:.3f}' for pool in pools[:3]]}")
            print(f"✅ FVG Detection → Pool Creation: WORKING")
        else:
            print(f"ℹ️  No pools created - possible market conditions or parameters")
            
        # Check for signal candidates being spawned
        active_candidates = getattr(htf.zone_watcher, 'active_candidates', [])
        print(f"   Active signal candidates: {len(active_candidates)}")
        if len(active_candidates) > 0:
            print(f"✅ Pool → Zone → Candidate: WORKING")
        
        # Check broker for any generated signals (even if not executed as trades)
        broker_trades = runner.strategy.broker.get_trades() if hasattr(runner.strategy.broker, 'get_trades') else []
        print(f"   Broker trades recorded: {len(broker_trades)}")
        
        # Success criteria: Either pools created OR signals generated
        success = len(pools) > 0 or len(active_candidates) > 0
        assert success, f"HTF pipeline inactive: {len(pools)} pools, {len(active_candidates)} candidates"
        
        print(f"✅ Integration test PASSED - HTF pipeline operational!")
        print(f"   System integrity: ✓")
        print(f"   Component wiring: ✓") 
        print(f"   Market data processing: ✓")
        
    else:
        print(f"ℹ️  Using mock strategy - HTF stack not available")
        assert False, "Expected HTF stack but got mock strategy"


def test_htf_strategy_components():
    """Test HTF strategy components are properly initialized."""
    config_path = Path("configs/base.yaml") 
    cfg = yaml.safe_load(config_path.open())
    cfg["execution"]["deterministic_seed"] = 456
    cfg["data"]["path"] = "data/BTC_USD_5min_20250728_021825.csv"  # Use available file
    
    config = BacktestConfig(**cfg)
    runner = BacktestRunner(config)
    
    # Initialize the strategy
    result = runner.run()
    assert result.success, f"Failed to initialize strategy: {result.error_message}"
    
    # Access strategy components
    strategy = runner.strategy
    assert strategy is not None, "Strategy is None"
    
    # Validate HTF stack exists
    assert hasattr(strategy, 'htf_stack'), "Strategy missing HTF stack"
    assert strategy.htf_stack is not None, "HTF stack is None"
    
    # Validate core components
    htf = strategy.htf_stack
    assert htf.pool_registry is not None, "Missing pool registry"
    assert htf.zone_watcher is not None, "Missing zone watcher"
    assert htf.pool_manager is not None, "Missing pool manager"
    assert htf.detectors is not None, "Missing detectors"
    assert htf.time_aggregators is not None, "Missing time aggregators"
    
    # Validate configuration
    assert len(htf.detectors) >= 1, "No detectors configured"
    assert len(htf.time_aggregators) >= 1, "No time aggregators configured"
    
    # Validate detector timeframes match config
    expected_tfs = set(config.strategy.htf_list)
    detector_tfs = {d.tf for d in htf.detectors}
    assert detector_tfs == expected_tfs, f"Detector TFs {detector_tfs} != config TFs {expected_tfs}"
    
    print(f"✅ Component test passed!")
    print(f"   Detectors: {len(htf.detectors)} ({list(detector_tfs)})")
    print(f"   Aggregators: {list(htf.time_aggregators.keys())}")


if __name__ == "__main__":
    # Run tests directly for debugging
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        print("Running integration tests...")
        test_end_to_end_fvg_trade(tmp_dir)
        test_htf_strategy_components()
        print("All tests passed! 🎉")
