#!/usr/bin/env python3
"""
Test script for Enhanced FVG Detection
Demonstrates the improved FVG filtering capabilities
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
from src.core.signals.fvg import detect_fvg
from src.core.signals.enhanced_fvg_detector import (
    detect_fvg_with_filters, 
    FVGFilterConfig, 
    FVGFilterPresets,
    get_fvg_quality_metrics
)
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal

def test_fvg_filtering():
    """Test FVG filtering with different configurations"""
    print("🧪 Testing Enhanced FVG Detection")
    print("=" * 50)
    
    # Initialize components
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    # Get sample data
    symbol = "BTC/USD"
    timeframe = "15T"
    
    try:
        # Get recent candles
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        # Get from cache first
        cache_key = f"bars_{symbol}_{timeframe}_{start_time.isoformat()}_{end_time.isoformat()}"
        cached_bars = redis.get(cache_key)
        
        if cached_bars:
            print("✅ Using cached candle data")
            import json
            candles = json.loads(cached_bars)
        else:
            print("📊 Fetching fresh candle data...")
            candles = repo.get_bars(symbol, timeframe, start_time, end_time)
            # Cache the result
            redis.set(cache_key, json.dumps(candles), ex=3600)
        
        print(f"📈 Analyzing {len(candles)} candles")
        
        # Test different filter configurations
        filter_configs = {
            "Original (No Filters)": None,
            "Conservative": FVGFilterPresets.conservative(),
            "Balanced": FVGFilterPresets.balanced(),
            "Aggressive": FVGFilterPresets.aggressive(),
            "Scalping": FVGFilterPresets.scalping()
        }
        
        print("\n🔍 FVG Detection Comparison:")
        print("-" * 60)
        print(f"{'Filter Type':<20} {'Total FVGs':<12} {'Avg Strength':<12} {'Quality %':<12}")
        print("-" * 60)
        
        for config_name, config in filter_configs.items():
            if config is None:
                # Original detection
                original_fvgs = detect_fvg(candles)
                total_fvgs = sum(1 for c in original_fvgs if c.get("fvg_zone"))
                avg_strength = 0.5  # Assumed average for original
                quality_rate = 0.5  # Assumed quality rate for original
            else:
                # Enhanced detection
                enhanced_fvgs = detect_fvg_with_filters(candles, config)
                total_fvgs = sum(1 for c in enhanced_fvgs if c.get("fvg_zone"))
                
                if total_fvgs > 0:
                    total_strength = sum(c.get("fvg_strength", 0) for c in enhanced_fvgs if c.get("fvg_zone"))
                    avg_strength = total_strength / total_fvgs
                    high_quality = sum(1 for c in enhanced_fvgs if c.get("fvg_strength", 0) >= 0.7)
                    quality_rate = high_quality / total_fvgs
                else:
                    avg_strength = 0.0
                    quality_rate = 0.0
            
            print(f"{config_name:<20} {total_fvgs:<12} {avg_strength:<12.2f} {quality_rate:<12.1%}")
        
        print("\n📊 Detailed Analysis with Balanced Filter:")
        print("-" * 50)
        
        # Get quality metrics for balanced filter
        metrics = get_fvg_quality_metrics(candles)
        
        print(f"Total FVGs detected: {metrics['total_fvgs']}")
        print(f"High-quality FVGs: {metrics['high_quality_fvgs']}")
        print(f"Quality rate: {metrics['quality_rate']:.1%}")
        print(f"Average strength: {metrics['average_strength']:.2f}")
        print(f"Current ATR: {metrics['atr']:.2f}")
        print(f"Current momentum: {metrics['momentum']:.2f}")
        print(f"In consolidation: {'Yes' if metrics['in_consolidation'] else 'No'}")
        
        # Show some examples of filtered FVGs
        balanced_fvgs = detect_fvg_with_filters(candles, FVGFilterPresets.balanced())
        high_quality_fvgs = [c for c in balanced_fvgs if c.get("fvg_strength", 0) >= 0.7]
        
        print(f"\n🎯 High-Quality FVG Examples (Strength >= 0.7):")
        print("-" * 60)
        
        for i, fvg in enumerate(high_quality_fvgs[:5]):  # Show first 5
            if fvg.get("fvg_zone"):
                direction = "Bullish" if fvg.get("fvg_bullish") else "Bearish"
                zone_size = abs(fvg["fvg_zone"][1] - fvg["fvg_zone"][0])
                
                print(f"  {i+1}. {direction} FVG")
                print(f"     Time: {fvg['timestamp']}")
                print(f"     Zone: {fvg['fvg_zone'][0]:.2f} - {fvg['fvg_zone'][1]:.2f}")
                print(f"     Size: {zone_size:.2f}")
                print(f"     Strength: {fvg.get('fvg_strength', 0):.2f}")
                print(f"     Price: {fvg['close']:.2f}")
                print()
        
        # Test with FVG Pool Manager
        print("\n🏊 Testing FVG Pool Manager with Enhanced Detection:")
        print("-" * 50)
        
        from src.core.liquidity.fvg_pool_manager import FVGPoolManager
        
        # Test different presets
        presets = ['conservative', 'balanced', 'aggressive']
        
        for preset in presets:
            fvg_manager = FVGPoolManager(db, redis)
            fvg_manager.set_filter_preset(preset)
            
            pools = fvg_manager.detect_pools(candles, symbol, timeframe)
            
            if pools:
                avg_strength = sum(p.strength for p in pools) / len(pools)
                print(f"  {preset.capitalize()} preset: {len(pools)} pools, avg strength: {avg_strength:.2f}")
            else:
                print(f"  {preset.capitalize()} preset: 0 pools detected")
        
        print("\n💡 Recommendations:")
        print("-" * 30)
        
        if metrics['in_consolidation']:
            print("  🔄 Market is in consolidation - consider using conservative filters")
        else:
            print("  📈 Market is trending - balanced or aggressive filters may work well")
        
        if metrics['momentum'] > 0.7:
            print("  🚀 High momentum detected - good for scalping filters")
        elif metrics['momentum'] < 0.3:
            print("  🐌 Low momentum - consider conservative filters")
        
        if metrics['quality_rate'] < 0.3:
            print("  ⚠️  Low quality rate - consider tightening filters")
        elif metrics['quality_rate'] > 0.7:
            print("  ✅ High quality rate - filters are working well")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def demonstrate_filter_customization():
    """Demonstrate how to customize FVG filters"""
    print("\n🔧 Custom FVG Filter Configuration")
    print("=" * 50)
    
    # Create custom configuration
    custom_config = FVGFilterConfig()
    
    # Customize for crypto trading
    custom_config.min_zone_size_pips = 20.0  # Larger zones for crypto volatility
    custom_config.min_zone_size_percentage = 0.025  # 2.5% minimum zone size
    custom_config.min_volume_multiplier = 1.5  # Require higher volume
    custom_config.min_strength_threshold = 0.65  # Slightly lower threshold
    custom_config.avoid_consolidation_fvgs = True  # Avoid consolidation
    custom_config.min_momentum_threshold = 0.4  # Moderate momentum requirement
    
    print("Custom Configuration:")
    print(f"  Min zone size (pips): {custom_config.min_zone_size_pips}")
    print(f"  Min zone size (%): {custom_config.min_zone_size_percentage:.1%}")
    print(f"  Min volume multiplier: {custom_config.min_volume_multiplier}")
    print(f"  Min strength threshold: {custom_config.min_strength_threshold}")
    print(f"  Avoid consolidation: {custom_config.avoid_consolidation_fvgs}")
    print(f"  Min momentum: {custom_config.min_momentum_threshold}")
    
    print("\n💡 This configuration is optimized for:")
    print("  - Cryptocurrency trading (larger zones)")
    print("  - Higher volume confirmation")
    print("  - Avoiding choppy market conditions")
    print("  - Moderate quality threshold")

if __name__ == "__main__":
    test_fvg_filtering()
    demonstrate_filter_customization()
    
    print("\n🎯 Enhanced FVG Detection Testing Complete!")
    print("Use the different filter presets based on your trading style:")
    print("  - Conservative: High-quality signals, fewer trades")
    print("  - Balanced: Good balance of quality and quantity")
    print("  - Aggressive: More signals, lower quality threshold")
    print("  - Scalping: Very selective for quick trades")
