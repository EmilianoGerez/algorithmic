# Refactored Signal Detection Architecture

## Overview

This document describes the refactored signal detection system with improved separation of concerns, better performance, and enhanced reusability for algorithmic trading strategies.

## Key Improvements

### 1. Separation of Concerns

- **Base Pool Manager**: Abstract foundation for all liquidity pool types
- **FVG Pool Manager**: Specialized for Fair Value Gap tracking
- **Pivot Pool Manager**: Specialized for swing point/pivot tracking
- **Multi-Timeframe Engine**: Orchestrates cross-timeframe analysis
- **Enhanced Cache Manager**: Optimized caching with multi-level support

### 2. Performance Optimizations

- **Multi-level Caching**: Memory + Redis for optimal performance
- **Batch Processing**: Efficient bulk operations
- **Lazy Loading**: Load data only when needed
- **Cleanup Mechanisms**: Automatic cleanup of old data

### 3. Real-Time Ready Architecture

- **Event-Driven Design**: Ready for streaming data
- **Stateless Components**: Easy to scale horizontally
- **Configurable Timeframes**: Support for any timeframe combination
- **Signal Expiration**: Automatic cleanup of old signals

## Architecture Components

### Core Components

#### 1. BaseLiquidityPoolManager

```python
from src.core.liquidity.base_pool_manager import BaseLiquidityPoolManager

# Abstract base class for all liquidity pool managers
# Provides common functionality for detection, tracking, and persistence
```

**Key Features:**

- Abstract methods for pool detection and status updates
- Common caching mechanisms
- Pool strength calculation
- Cleanup utilities

#### 2. FVGPoolManager

```python
from src.core.liquidity.fvg_pool_manager import FVGPoolManager

# Specialized manager for Fair Value Gap liquidity pools
fvg_manager = FVGPoolManager(db_session, cache_manager)
```

**Key Features:**

- FVG detection and tracking
- Inverse FVG detection
- Mitigation percentage calculation
- Touch count tracking
- HTF/LTF pool correlation

#### 3. PivotPoolManager

```python
from src.core.liquidity.pivot_pool_manager import PivotPoolManager

# Specialized manager for pivot point liquidity pools
pivot_manager = PivotPoolManager(db_session, cache_manager)
```

**Key Features:**

- Swing high/low detection
- Market structure analysis
- Pivot confirmation logic
- Support/resistance identification
- Confluence detection

#### 4. MultiTimeframeSignalEngine

```python
from src.core.signals.multi_timeframe_engine import MultiTimeframeSignalEngine

# Main engine for multi-timeframe analysis
engine = MultiTimeframeSignalEngine(repo, db_session, cache_manager)
```

**Key Features:**

- HTF context analysis
- LTF signal detection
- Signal strength scoring
- Confidence calculation
- Entry/exit level calculation

#### 5. Enhanced Cache Manager

```python
from src.infrastructure.cache.enhanced_cache_manager import CacheManager

# Multi-level caching system
cache = CacheManager(redis_client, use_memory_cache=True)
```

**Key Features:**

- Memory + Redis caching
- Automatic expiration
- Pattern-based invalidation
- Cache statistics
- Error resilience

### Signal Types

The system supports multiple signal types:

```python
class SignalType(Enum):
    FVG_RETEST = "fvg_retest"           # HTF FVG retest with LTF confirmation
    PIVOT_BOUNCE = "pivot_bounce"       # Bounce from significant pivot
    STRUCTURE_BREAK = "structure_break" # Market structure break
    CISD_ENTRY = "cisd_entry"          # Change in State of Delivery
    INVERSE_FVG = "inverse_fvg"        # Inverse FVG after liquidity grab
    LIQUIDITY_GRAB = "liquidity_grab"  # Liquidity pool interaction
```

### Strategy Types

Predefined strategy configurations:

```python
timeframe_configs = {
    "scalping": {"ltf": "5T", "htf": "1H"},     # 5min entries, 1H context
    "intraday": {"ltf": "15T", "htf": "4H"},    # 15min entries, 4H context
    "swing": {"ltf": "1H", "htf": "1D"},        # 1H entries, daily context
    "position": {"ltf": "4H", "htf": "1W"}      # 4H entries, weekly context
}
```

## Usage Examples

### Basic Signal Detection

```python
from src.services.signal_detection import SignalDetectionService

# Initialize service
service = SignalDetectionService(repo, redis, db)

# Detect signals using new multi-timeframe approach
signals = service.detect_multi_timeframe_signals(
    symbol="BTC/USD",
    strategy_type="intraday",
    start="2025-01-10T00:00:00Z",
    end="2025-01-15T00:00:00Z",
    update_pools=True
)

# Process signals
for signal in signals:
    print(f"Signal: {signal.signal_type.value}")
    print(f"Direction: {signal.direction}")
    print(f"Price: ${signal.price:.2f}")
    print(f"Strength: {signal.strength.name}")
    print(f"Confidence: {signal.confidence:.2f}")
    print(f"Entry: ${signal.entry_price:.2f}")
    print(f"Stop Loss: ${signal.stop_loss:.2f}")
    print(f"Take Profit: ${signal.take_profit:.2f}")
```

### Liquidity Pool Management

```python
# Get active liquidity pools
htf_pools = service.get_liquidity_pools("BTC/USD", "4H", "all")

# FVG pools
for pool in htf_pools["fvg_pools"]:
    print(f"FVG {pool['direction']}: ${pool['zone_low']:.2f} - ${pool['zone_high']:.2f}")

# Pivot pools
for pool in htf_pools["pivot_pools"]:
    print(f"Pivot {pool['pivot_type']}: ${pool['price_level']:.2f}")

# Update pools with new data
update_stats = service.update_liquidity_pools("BTC/USD", "1H", start, end)
print(f"Updated {update_stats['fvg_pools_updated']} FVG pools")
print(f"Updated {update_stats['pivot_pools_updated']} pivot pools")
```

### Real-Time Implementation

```python
# Example real-time update cycle
def real_time_update():
    # Every minute: detect new signals
    signals = service.detect_multi_timeframe_signals(
        symbol="BTC/USD",
        strategy_type="intraday",
        start=get_last_hour(),
        end=get_current_time(),
        update_pools=False  # Don't update pools every minute
    )

    # Process new signals
    for signal in signals:
        if signal.strength.value >= 3:  # Only strong signals
            send_alert(signal)

    return signals

# Every 15 minutes: update LTF pools
def update_ltf_pools():
    service.update_liquidity_pools("BTC/USD", "15T", get_last_4_hours(), get_current_time())

# Every 4 hours: update HTF pools
def update_htf_pools():
    service.update_liquidity_pools("BTC/USD", "4H", get_last_week(), get_current_time())

# Daily: cleanup old data
def daily_cleanup():
    service.cleanup_old_data(days_old=7)
```

## Performance Benefits

### 1. Caching Improvements

- **Memory cache**: Fastest access for frequently used data
- **Redis cache**: Shared cache across instances
- **Intelligent invalidation**: Only invalidate when necessary
- **Cache statistics**: Monitor cache performance

### 2. Database Optimizations

- **Bulk operations**: Batch inserts/updates
- **Selective updates**: Only update changed data
- **Efficient queries**: Optimized database queries
- **Connection pooling**: Reuse database connections

### 3. Algorithmic Performance

- **Vectorized operations**: Use NumPy where possible
- **Lazy evaluation**: Compute only when needed
- **Parallel processing**: Multi-threading for independent operations
- **Memory management**: Efficient memory usage

## Migration Guide

### For Existing Code

The refactored system maintains backwards compatibility:

```python
# Old way (still works)
result = service.detect_signals(
    symbol="BTC/USD",
    signal_type="fvg_and_pivot",
    timeframe="15T",
    start=start,
    end=end
)

# New way (recommended)
signals = service.detect_multi_timeframe_signals(
    symbol="BTC/USD",
    strategy_type="intraday",
    start=start,
    end=end
)
```

### Gradual Migration Steps

1. **Phase 1**: Use new caching system
2. **Phase 2**: Migrate to new pool managers
3. **Phase 3**: Adopt multi-timeframe engine
4. **Phase 4**: Implement real-time updates

## Future Enhancements

### 1. Advanced Features

- **Machine learning integration**: ML-based signal scoring
- **Risk management**: Integrated position sizing
- **Portfolio analysis**: Multi-symbol coordination
- **Backtesting framework**: Historical strategy validation

### 2. Scalability

- **Microservices**: Split into independent services
- **Message queues**: Async communication
- **Load balancing**: Distribute processing
- **Auto-scaling**: Dynamic resource allocation

### 3. Monitoring & Analytics

- **Performance metrics**: Detailed system monitoring
- **Signal analytics**: Success rate tracking
- **Alert systems**: Real-time notifications
- **Dashboard**: Visual system overview

## Best Practices

### 1. Pool Management

- Update HTF pools less frequently (every 4 hours)
- Update LTF pools more frequently (every 15 minutes)
- Clean up old pools regularly
- Monitor pool performance metrics

### 2. Signal Detection

- Use appropriate timeframe combinations
- Filter signals by strength and confidence
- Implement proper risk management
- Track signal success rates

### 3. Performance

- Use caching extensively
- Batch database operations
- Monitor memory usage
- Optimize query patterns

### 4. Real-Time Implementation

- Implement proper error handling
- Use circuit breakers for external APIs
- Monitor system health
- Implement graceful degradation

## Testing

### Unit Tests

```python
# Test individual components
def test_fvg_pool_manager():
    manager = FVGPoolManager(db, cache)
    pools = manager.detect_pools(test_candles, "BTC/USD", "4H")
    assert len(pools) > 0

def test_signal_detection():
    engine = MultiTimeframeSignalEngine(repo, db, cache)
    signals = engine.detect_signals("BTC/USD", "intraday")
    assert all(s.confidence > 0 for s in signals)
```

### Integration Tests

```python
# Test complete workflows
def test_multi_timeframe_flow():
    service = SignalDetectionService(repo, redis, db)
    signals = service.detect_multi_timeframe_signals("BTC/USD", "intraday")
    assert len(signals) >= 0
```

### Performance Tests

```python
# Test system performance
def test_cache_performance():
    # Measure cache hit rates
    # Test memory usage
    # Validate response times
```

## Conclusion

The refactored architecture provides:

1. **Better separation of concerns** - Each component has a clear responsibility
2. **Improved performance** - Multi-level caching and optimized algorithms
3. **Enhanced reusability** - Components can be used independently
4. **Real-time readiness** - Architecture supports live data streaming
5. **Scalability** - Easy to scale horizontally and vertically
6. **Maintainability** - Clean, well-documented code structure

This foundation enables building sophisticated algorithmic trading systems that can handle high-frequency data processing while maintaining code quality and performance.
