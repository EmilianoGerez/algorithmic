"""Strategy components for multi-timeframe analysis."""

from .aggregator import MultiTimeframeAggregator, TimeAggregator

# Phase 5: Overlap Detection & HLZ
from .overlap import OverlapConfig, OverlapDetector, OverlapIndex, OverlapResult
from .pool_manager import EventMappingResult, PoolManager, PoolManagerConfig

# Phase 4: Pool Registry & TTL Management
from .pool_models import (
    HighLiquidityZone,
    HLZCreatedEvent,
    HLZExpiredEvent,
    HLZUpdatedEvent,
    LiquidityPool,
    PoolCreatedEvent,
    PoolExpiredEvent,
    PoolState,
    PoolTouchedEvent,
    generate_hlz_id,
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
    # Pool models & events (Phase 4)
    "LiquidityPool",
    "PoolState",
    "PoolCreatedEvent",
    "PoolTouchedEvent",
    "PoolExpiredEvent",
    "generate_pool_id",
    # HLZ models & events (Phase 5)
    "HighLiquidityZone",
    "HLZCreatedEvent",
    "HLZUpdatedEvent",
    "HLZExpiredEvent",
    "generate_hlz_id",
    # Pool registry (Phase 4)
    "PoolRegistry",
    "PoolRegistryConfig",
    "PoolRegistryMetrics",
    # Pool management
    "PoolManager",
    "PoolManagerConfig",
    "EventMappingResult",
    # Overlap detection (Phase 5)
    "OverlapDetector",
    "OverlapConfig",
    "OverlapIndex",
    "OverlapResult",
    # TTL wheel
    "TimerWheel",
    "WheelConfig",
    "ScheduledExpiry",
]
