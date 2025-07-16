"""
Example script demonstrating the refactored multi-timeframe signal detection system

This script shows how to use the new architecture for:
- Multi-timeframe analysis
- Liquidity pool management
- Advanced signal detection
- Real-time ready implementation

Key improvements:
- Separation of concerns
- Better caching
- Reusable components
- Performance optimizations
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta, timezone
from src.services.signal_detection import SignalDetectionService
from src.infrastructure.data.alpaca import AlpacaCryptoRepository
from src.infrastructure.cache.redis import get_redis_connection
from src.db.session import SessionLocal


def main():
    """Main function demonstrating the refactored system"""
    
    # Initialize components
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    
    # Initialize the refactored service
    service = SignalDetectionService(repo, redis, db)
    
    # Configuration
    symbol = "BTC/USD"
    start = "2025-05-18T00:00:00Z"
    end = "2025-05-22T00:00:00Z"
    
    print("🚀 Refactored Multi-Timeframe Signal Detection System")
    print("=" * 60)
    
    # 1. Demonstrate multi-timeframe signal detection
    print("\n1. Multi-Timeframe Signal Detection")
    print("-" * 40)
    
    # Test different strategy types
    strategy_types = ["scalping", "intraday", "swing"]
    
    for strategy in strategy_types:
        print(f"\n📊 Testing {strategy} strategy:")
        
        signals = service.detect_multi_timeframe_signals(
            symbol=symbol,
            strategy_type=strategy,
            start=start,
            end=end,
            update_pools=True
        )
        
        print(f"   Found {len(signals)} signals")
        
        # Display top 3 signals
        for i, signal in enumerate(signals[:3]):
            print(f"   {i+1}. {signal.signal_type.value} - {signal.direction} - "
                  f"Price: ${signal.price:.2f} - Strength: {signal.strength.name} - "
                  f"Confidence: {signal.confidence:.2f}")
    
    # 2. Demonstrate liquidity pool management
    print("\n\n2. Liquidity Pool Management")
    print("-" * 40)
    
    # Get HTF liquidity pools
    htf_pools = service.get_liquidity_pools(symbol, "4H", "all")
    
    print(f"📈 HTF (4H) Liquidity Pools:")
    print(f"   FVG Pools: {len(htf_pools.get('fvg_pools', []))}")
    print(f"   Pivot Pools: {len(htf_pools.get('pivot_pools', []))}")
    
    # Display some FVG pools
    for i, pool in enumerate(htf_pools.get('fvg_pools', [])[:3]):
        print(f"   FVG {i+1}: {pool['direction']} - "
              f"Zone: ${pool['zone_low']:.2f} - ${pool['zone_high']:.2f} - "
              f"Status: {pool['status']} - Strength: {pool['strength']:.2f}")
    
    # Display some pivot pools
    for i, pool in enumerate(htf_pools.get('pivot_pools', [])[:3]):
        print(f"   Pivot {i+1}: {pool['pivot_type']} - "
              f"Price: ${pool['price_level']:.2f} - "
              f"Status: {pool['status']} - Strength: {pool['strength']:.2f}")
    
    # 3. Demonstrate pool updates
    print("\n\n3. Pool Update Statistics")
    print("-" * 40)
    
    update_stats = service.update_liquidity_pools(symbol, "1H", start, end)
    
    print(f"📊 Pool Update Results:")
    print(f"   FVG pools updated: {update_stats['fvg_pools_updated']}")
    print(f"   Pivot pools updated: {update_stats['pivot_pools_updated']}")
    print(f"   Candles processed: {update_stats['candles_processed']}")
    print(f"   FVG save success: {update_stats['fvg_save_success']}")
    print(f"   Pivot save success: {update_stats['pivot_save_success']}")
    
    # 4. Demonstrate signal history
    print("\n\n4. Signal History")
    print("-" * 40)
    
    signal_history = service.get_signal_history(symbol, hours_back=24)
    
    print(f"📜 Signal History (last 24h): {len(signal_history)} signals")
    
    # Group by signal type
    signal_types = {}
    for signal in signal_history:
        signal_type = signal['signal_type']
        if signal_type not in signal_types:
            signal_types[signal_type] = []
        signal_types[signal_type].append(signal)
    
    for signal_type, signals in signal_types.items():
        print(f"   {signal_type}: {len(signals)} signals")
    
    # 5. Demonstrate cache statistics
    print("\n\n5. Cache Performance")
    print("-" * 40)
    
    cache_stats = service.get_cache_stats()
    
    print(f"💾 Cache Statistics:")
    print(f"   Memory cache size: {cache_stats['memory_cache_size']}")
    print(f"   Redis connected: {cache_stats['redis_connected']}")
    print(f"   Expired entries cleaned: {cache_stats['expired_cleaned']}")
    
    if 'redis_keys' in cache_stats:
        print(f"   Redis keys: {cache_stats['redis_keys']}")
        print(f"   Redis memory usage: {cache_stats['redis_memory']}")
    
    # 6. Demonstrate cleanup
    print("\n\n6. Data Cleanup")
    print("-" * 40)
    
    cleanup_stats = service.cleanup_old_data(days_old=30)
    
    print(f"🧹 Cleanup Statistics:")
    print(f"   FVG pools removed: {cleanup_stats['fvg_pools_removed']}")
    print(f"   Pivot pools removed: {cleanup_stats['pivot_pools_removed']}")
    print(f"   Cache entries cleaned: {cleanup_stats['cache_entries_cleaned']}")
    
    # 7. Demonstrate backwards compatibility
    print("\n\n7. Backwards Compatibility")
    print("-" * 40)
    
    # Test the legacy method
    legacy_result = service.detect_signals(
        symbol=symbol,
        signal_type="fvg_and_pivot",
        timeframe="15T",
        start=start,
        end=end
    )
    
    print(f"🔄 Legacy Method Results:")
    print(f"   Candles: {len(legacy_result['candles'])}")
    print(f"   Tracked FVGs: {len(legacy_result['tracked_fvgs'])}")
    print(f"   Pivots: {len(legacy_result['pivots'])}")
    print(f"   Signals: {len(legacy_result['signals'])}")
    
    print("\n" + "=" * 60)
    print("✅ Refactored system demonstration complete!")
    print("\nKey Benefits:")
    print("• Separation of concerns - each component has a specific responsibility")
    print("• Better caching - enhanced performance with multi-level caching")
    print("• Reusable components - pool managers can be used independently")
    print("• Real-time ready - architecture supports live data streaming")
    print("• Algorithmic performance - optimized for high-frequency analysis")
    print("• Multi-timeframe analysis - HTF context with LTF entries")
    print("• Backwards compatibility - existing code continues to work")
    
    # Close database connection
    db.close()


def demonstrate_real_time_scenario():
    """
    Demonstrate how the system would work in a real-time scenario
    """
    print("\n🔴 Real-Time Scenario Simulation")
    print("-" * 40)
    
    # This would be called periodically (e.g., every minute) in real-time
    repo = AlpacaCryptoRepository()
    redis = get_redis_connection()
    db = SessionLocal()
    service = SignalDetectionService(repo, redis, db)
    
    symbol = "BTC/USD"
    
    # Simulate real-time updates
    print("🔄 Real-time update cycle:")
    print("1. Update HTF liquidity pools (every 4 hours)")
    print("2. Update LTF pools (every 15 minutes)")
    print("3. Detect new signals (every minute)")
    print("4. Clean up expired data (daily)")
    
    # Example of what would run every minute
    # Use historical dates that have data available
    current_time = datetime(2024, 12, 5, 12, 0, 0, tzinfo=timezone.utc)
    start_time = current_time - timedelta(hours=1)
    
    # Format timestamps for Alpaca API (remove timezone info, just use Z)
    start_str = start_time.replace(tzinfo=None).isoformat() + "Z"
    end_str = current_time.replace(tzinfo=None).isoformat() + "Z"
    
    signals = service.detect_multi_timeframe_signals(
        symbol=symbol,
        strategy_type="intraday",
        start=start_str,
        end=end_str,
        update_pools=False  # Don't update pools every minute
    )
    
    print(f"📊 Real-time signals detected: {len(signals)}")
    
    for signal in signals:
        print(f"   🚨 {signal.signal_type.value} - {signal.direction} - "
              f"${signal.price:.2f} - {signal.strength.name}")
    
    db.close()


if __name__ == "__main__":
    main()
    demonstrate_real_time_scenario()
