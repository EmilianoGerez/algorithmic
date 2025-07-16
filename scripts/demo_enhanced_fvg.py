#!/usr/bin/env python3
"""
Enhanced FVG Detection Demo
Uses existing cached data or mock data to demonstrate FVG filtering
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
import json
from src.core.signals.fvg import detect_fvg
from src.core.signals.enhanced_fvg_detector import (
    detect_fvg_with_filters, 
    FVGFilterConfig, 
    FVGFilterPresets,
    get_fvg_quality_metrics
)
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal

def generate_sample_candles():
    """Generate sample candle data for testing"""
    base_price = 45000.0
    candles = []
    
    current_time = datetime.now() - timedelta(hours=24)
    
    for i in range(100):
        # Create some volatility patterns
        price_move = (i % 20 - 10) * 50  # Oscillating price movement
        trend = i * 2  # Slight upward trend
        
        open_price = base_price + trend + price_move
        close_price = open_price + ((-1) ** i) * 30  # Alternating green/red candles
        
        high_price = max(open_price, close_price) + abs(price_move) * 0.3
        low_price = min(open_price, close_price) - abs(price_move) * 0.3
        
        volume = 1000 + (i % 10) * 200  # Varying volume
        
        candle = {
            "timestamp": (current_time + timedelta(minutes=i*15)).isoformat() + "Z",
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume
        }
        candles.append(candle)
    
    return candles

def test_fvg_filtering_with_sample_data():
    """Test FVG filtering with sample data"""
    print("🧪 Enhanced FVG Detection Demo")
    print("=" * 50)
    
    # Generate sample candles
    candles = generate_sample_candles()
    print(f"📈 Generated {len(candles)} sample candles")
    
    # Test different filter configurations
    filter_configs = {
        "Original (No Filters)": None,
        "Conservative": FVGFilterPresets.conservative(),
        "Balanced": FVGFilterPresets.balanced(),
        "Aggressive": FVGFilterPresets.aggressive(),
        "Scalping": FVGFilterPresets.scalping()
    }
    
    print("\n🔍 FVG Detection Comparison:")
    print("-" * 70)
    print(f"{'Filter Type':<20} {'Total FVGs':<12} {'Avg Strength':<12} {'Quality %':<12} {'Notes':<20}")
    print("-" * 70)
    
    results = {}
    
    for config_name, config in filter_configs.items():
        if config is None:
            # Original detection
            original_fvgs = detect_fvg(candles)
            total_fvgs = sum(1 for c in original_fvgs if c.get("fvg_zone"))
            avg_strength = 0.5  # Assumed average for original
            quality_rate = 0.5  # Assumed quality rate for original
            notes = "No filtering"
        else:
            # Enhanced detection
            enhanced_fvgs = detect_fvg_with_filters(candles, config)
            total_fvgs = sum(1 for c in enhanced_fvgs if c.get("fvg_zone"))
            
            if total_fvgs > 0:
                total_strength = sum(c.get("fvg_strength", 0) for c in enhanced_fvgs if c.get("fvg_zone"))
                avg_strength = total_strength / total_fvgs
                high_quality = sum(1 for c in enhanced_fvgs if c.get("fvg_strength", 0) >= 0.7)
                quality_rate = high_quality / total_fvgs
                notes = f"Min strength: {config.min_strength_threshold}"
            else:
                avg_strength = 0.0
                quality_rate = 0.0
                notes = "No FVGs found"
        
        results[config_name] = {
            'total': total_fvgs,
            'avg_strength': avg_strength,
            'quality_rate': quality_rate
        }
        
        print(f"{config_name:<20} {total_fvgs:<12} {avg_strength:<12.2f} {quality_rate:<12.1%} {notes:<20}")
    
    # Detailed analysis with balanced filter
    print("\n📊 Detailed Analysis with Balanced Filter:")
    print("-" * 50)
    
    balanced_config = FVGFilterPresets.balanced()
    metrics = get_fvg_quality_metrics(candles)
    
    print(f"Total FVGs detected: {metrics['total_fvgs']}")
    print(f"High-quality FVGs: {metrics['high_quality_fvgs']}")
    print(f"Quality rate: {metrics['quality_rate']:.1%}")
    print(f"Average strength: {metrics['average_strength']:.2f}")
    print(f"Current ATR: {metrics['atr']:.2f}")
    print(f"Current momentum: {metrics['momentum']:.2f}")
    print(f"In consolidation: {'Yes' if metrics['in_consolidation'] else 'No'}")
    
    # Show filter configuration details
    print(f"\n🔧 Balanced Filter Configuration:")
    print(f"  Min zone size (pips): {balanced_config.min_zone_size_pips}")
    print(f"  Min zone size (%): {balanced_config.min_zone_size_percentage:.1%}")
    print(f"  Min ATR multiplier: {balanced_config.min_zone_size_atr_multiplier}")
    print(f"  Min volume multiplier: {balanced_config.min_volume_multiplier}")
    print(f"  Min strength threshold: {balanced_config.min_strength_threshold}")
    print(f"  Avoid consolidation: {balanced_config.avoid_consolidation_fvgs}")
    print(f"  Min momentum: {balanced_config.min_momentum_threshold}")
    
    # Show examples of filtered FVGs
    balanced_fvgs = detect_fvg_with_filters(candles, balanced_config)
    high_quality_fvgs = [c for c in balanced_fvgs if c.get("fvg_strength", 0) >= 0.7]
    
    print(f"\n🎯 High-Quality FVG Examples (Strength >= 0.7):")
    print("-" * 60)
    
    if high_quality_fvgs:
        for i, fvg in enumerate(high_quality_fvgs[:5]):  # Show first 5
            if fvg.get("fvg_zone"):
                direction = "Bullish" if fvg.get("fvg_bullish") else "Bearish"
                zone_size = abs(fvg["fvg_zone"][1] - fvg["fvg_zone"][0])
                zone_percentage = zone_size / fvg["close"] * 100
                
                print(f"  {i+1}. {direction} FVG")
                print(f"     Time: {fvg['timestamp']}")
                print(f"     Zone: {fvg['fvg_zone'][0]:.2f} - {fvg['fvg_zone'][1]:.2f}")
                print(f"     Size: {zone_size:.2f} ({zone_percentage:.2f}%)")
                print(f"     Strength: {fvg.get('fvg_strength', 0):.2f}")
                print(f"     Price: {fvg['close']:.2f}")
                print(f"     Volume: {fvg['volume']}")
                print()
    else:
        print("  No high-quality FVGs found in sample data")
    
    return results

def test_fvg_pool_manager():
    """Test FVG Pool Manager with enhanced detection"""
    print("\n🏊 Testing FVG Pool Manager with Enhanced Detection:")
    print("-" * 50)
    
    try:
        from src.core.liquidity.fvg_pool_manager import FVGPoolManager
        
        # Initialize with database
        db = SessionLocal()
        redis = get_redis_connection()
        
        # Test different presets
        presets = ['conservative', 'balanced', 'aggressive', 'scalping']
        candles = generate_sample_candles()
        symbol = "BTC/USD"
        timeframe = "15T"
        
        print(f"Testing with {len(candles)} sample candles...")
        print()
        
        for preset in presets:
            try:
                fvg_manager = FVGPoolManager(db, redis)
                fvg_manager.set_filter_preset(preset)
                
                pools = fvg_manager.detect_pools(candles, symbol, timeframe)
                
                if pools:
                    avg_strength = sum(p.strength for p in pools) / len(pools)
                    strong_pools = [p for p in pools if p.strength >= 0.7]
                    
                    print(f"  📊 {preset.capitalize()} preset:")
                    print(f"     Total pools: {len(pools)}")
                    print(f"     Avg strength: {avg_strength:.2f}")
                    print(f"     Strong pools (>=0.7): {len(strong_pools)}")
                    print(f"     Filter threshold: {fvg_manager.filter_config.min_strength_threshold}")
                    print()
                else:
                    print(f"  📊 {preset.capitalize()} preset: No pools detected")
                    print()
                    
            except Exception as e:
                print(f"  ❌ Error with {preset} preset: {e}")
                print()
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error testing FVG Pool Manager: {e}")

def demonstrate_custom_configuration():
    """Demonstrate custom FVG filter configuration"""
    print("\n🔧 Custom FVG Filter Configuration Examples:")
    print("-" * 50)
    
    # Example 1: Crypto day trading
    crypto_config = FVGFilterConfig()
    crypto_config.min_zone_size_pips = 25.0
    crypto_config.min_zone_size_percentage = 0.03  # 3%
    crypto_config.min_volume_multiplier = 1.8
    crypto_config.min_strength_threshold = 0.7
    crypto_config.avoid_consolidation_fvgs = True
    crypto_config.min_momentum_threshold = 0.6
    
    print("💰 Crypto Day Trading Configuration:")
    print(f"  Min zone size: {crypto_config.min_zone_size_pips} pips")
    print(f"  Min zone %: {crypto_config.min_zone_size_percentage:.1%}")
    print(f"  Volume multiplier: {crypto_config.min_volume_multiplier}x")
    print(f"  Strength threshold: {crypto_config.min_strength_threshold}")
    print(f"  Avoid consolidation: {crypto_config.avoid_consolidation_fvgs}")
    print(f"  Min momentum: {crypto_config.min_momentum_threshold}")
    
    # Example 2: Conservative swing trading
    swing_config = FVGFilterConfig()
    swing_config.min_zone_size_pips = 50.0
    swing_config.min_zone_size_percentage = 0.05  # 5%
    swing_config.min_volume_multiplier = 2.0
    swing_config.min_strength_threshold = 0.8
    swing_config.avoid_consolidation_fvgs = True
    swing_config.min_momentum_threshold = 0.8
    
    print("\n📈 Conservative Swing Trading Configuration:")
    print(f"  Min zone size: {swing_config.min_zone_size_pips} pips")
    print(f"  Min zone %: {swing_config.min_zone_size_percentage:.1%}")
    print(f"  Volume multiplier: {swing_config.min_volume_multiplier}x")
    print(f"  Strength threshold: {swing_config.min_strength_threshold}")
    print(f"  Avoid consolidation: {swing_config.avoid_consolidation_fvgs}")
    print(f"  Min momentum: {swing_config.min_momentum_threshold}")
    
    # Test both configurations
    candles = generate_sample_candles()
    
    print("\n🧪 Testing Custom Configurations:")
    print("-" * 40)
    
    configs = [
        ("Crypto Day Trading", crypto_config),
        ("Conservative Swing", swing_config)
    ]
    
    for name, config in configs:
        enhanced_fvgs = detect_fvg_with_filters(candles, config)
        total_fvgs = sum(1 for c in enhanced_fvgs if c.get("fvg_zone"))
        
        if total_fvgs > 0:
            avg_strength = sum(c.get("fvg_strength", 0) for c in enhanced_fvgs if c.get("fvg_zone")) / total_fvgs
            high_quality = sum(1 for c in enhanced_fvgs if c.get("fvg_strength", 0) >= 0.7)
            quality_rate = high_quality / total_fvgs
        else:
            avg_strength = 0.0
            quality_rate = 0.0
        
        print(f"  {name}: {total_fvgs} FVGs, {avg_strength:.2f} avg strength, {quality_rate:.1%} quality")

def main():
    """Main demonstration function"""
    print("🚀 Enhanced FVG Detection System Demo")
    print("=" * 60)
    
    # Test with sample data
    results = test_fvg_filtering_with_sample_data()
    
    # Test FVG Pool Manager
    test_fvg_pool_manager()
    
    # Demonstrate custom configurations
    demonstrate_custom_configuration()
    
    print("\n💡 Key Benefits of Enhanced FVG Detection:")
    print("-" * 50)
    print("  ✅ Filters out tiny, insignificant FVGs")
    print("  ✅ Considers volume confirmation")
    print("  ✅ Avoids consolidation periods")
    print("  ✅ Momentum-based filtering")
    print("  ✅ Customizable for different trading styles")
    print("  ✅ Strength scoring for better prioritization")
    print("  ✅ ATR-based zone size validation")
    print("  ✅ Multiple preset configurations")
    
    print("\n🎯 Usage Recommendations:")
    print("-" * 30)
    print("  • Conservative: High-probability setups, fewer signals")
    print("  • Balanced: Good balance for most strategies")
    print("  • Aggressive: More signals, suitable for active trading")
    print("  • Scalping: Very selective, high-frequency trading")
    print("  • Custom: Tailor to your specific requirements")
    
    print("\n✅ Enhanced FVG Detection Demo Complete!")

if __name__ == "__main__":
    main()
