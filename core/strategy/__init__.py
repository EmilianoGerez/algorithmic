"""Strategy components for multi-timeframe analysis."""

from .aggregator import MultiTimeframeAggregator, TimeAggregator
from .pool_manager import EventMappingResult, PoolManager, PoolManagerConfig

# Phase 4: Pool Registry & TTL Management
from .pool_models import (
    LiquidityPool,
    PoolCreatedEvent,
    PoolExpiredEvent,
    PoolState,
    PoolTouchedEvent,
    generate_pool_id,
)
from .pool_registry import PoolRegistry, PoolRegistryConfig, PoolRegistryMetrics
from .ring_buffer import CandleBuffer, RingBuffer
from .timeframe import (
    TimeframeConfig,
    format_timeframe_name,
    get_bucket_id,
    get_bucket_start,
)
from .ttl_wheel import ScheduledExpiry, TimerWheel, WheelConfig

__all__ = [
    # Timeframe utilities
    "TimeframeConfig",
    "get_bucket_id",
    "get_bucket_start",
    "format_timeframe_name",
    # Ring buffer components
    "RingBuffer",
    "CandleBuffer",
    # Aggregation components
    "TimeAggregator",
    "MultiTimeframeAggregator",
]
