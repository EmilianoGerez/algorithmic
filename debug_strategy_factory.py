#!/usr/bin/env python3
"""Debug the strategy factory HTF wiring specifically."""

import yaml
from services.models import BacktestConfig
from core.strategy.factory import StrategyFactory

def debug_strategy_factory():
    """Debug the strategy factory initialization."""
    print("=== Strategy Factory Debug ===")
    
    # Load the actual config
    with open("configs/binance.yaml", "r") as f:
        config_dict = yaml.safe_load(f)
    
    # Convert to BacktestConfig
    config = BacktestConfig(**config_dict)
    
    print(f"Config loaded: {config.strategy.name}")
    print(f"HTF list: {config.strategy.htf_list}")
    print(f"Aggregation config: {config.aggregation}")
    print(f"Detectors config: {config.detectors}")
    print(f"Pools config: {config.pools}")
    
    # Build strategy using factory
    print("\n=== Building Strategy ===")
    
    try:
        strategy = StrategyFactory.build(config)
        print("✅ Strategy created successfully")
        
        # Check HTF stack components
        if hasattr(strategy, 'htf_stack') and strategy.htf_stack:
            htf = strategy.htf_stack
            print(f"✅ HTF Stack exists")
            
            # Check time aggregators
            if htf.time_aggregators:
                print(f"✅ Time aggregators: {list(htf.time_aggregators.keys())}")
            else:
                print("❌ No time aggregators")
                
            # Check detectors 
            if htf.detectors:
                print(f"✅ Detectors: {len(htf.detectors)} detectors")
                for i, detector in enumerate(htf.detectors):
                    print(f"   {i}: {type(detector).__name__} tf={getattr(detector, 'tf', 'unknown')}")
            else:
                print("❌ No detectors")
                
            # Check pool manager
            if htf.pool_manager:
                print(f"✅ Pool manager exists")
                ttls = htf.pool_manager.config.ttl_by_timeframe if hasattr(htf.pool_manager, 'config') else {}
                print(f"   TTL config: {ttls}")
            else:
                print("❌ No pool manager")
                
            # Check pool registry
            if htf.pool_registry:
                print(f"✅ Pool registry exists")
            else:
                print("❌ No pool registry")
                
        else:
            print("❌ No HTF stack - using mock strategy")
            
    except Exception as e:
        print(f"❌ Strategy creation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_strategy_factory()
