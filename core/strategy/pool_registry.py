"""
High-performance liquidity pool registry with TTL management.

Provides O(1) CRUD operations for liquidity pools with automatic expiry
via TTL wheel. Supports multi-timeframe isolation and grace periods.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from .pool_models import (
    LiquidityPool,
    PoolExpiredEvent,
    PoolState,
    generate_pool_id,
)
from .ttl_wheel import TimerWheel, WheelConfig

__all__ = ["PoolRegistry", "PoolRegistryConfig", "PoolRegistryMetrics"]


logger = logging.getLogger(__name__)


class PoolRegistryConfig:
    """Configuration for pool registry behavior."""

    def __init__(
        self,
        grace_period_minutes: int = 5,
        enable_metrics: bool = True,
        max_pools_per_tf: int = 10000,
        cleanup_interval_minutes: int = 60,
    ):
        """
        Initialize pool registry configuration.

        Args:
            grace_period_minutes: Keep expired pools for analytics
            enable_metrics: Enable Prometheus-style metrics collection
            max_pools_per_tf: Maximum pools per timeframe (memory safety)
            cleanup_interval_minutes: How often to clean grace period pools
        """
        self.grace_period = timedelta(minutes=grace_period_minutes)
        self.enable_metrics = enable_metrics
        self.max_pools_per_tf = max_pools_per_tf
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)


class PoolRegistryMetrics:
    """Metrics collector for pool registry operations."""

    def __init__(self) -> None:
        """Initialize metrics tracking."""
        self.reset()

    def reset(self) -> None:
        """Reset all metrics to zero."""
        # Pool lifecycle counters
        self.pools_created = 0
        self.pools_touched = 0
        self.pools_expired = 0
        self.pools_cleaned = 0

        # Performance counters
        self.add_operations = 0
        self.touch_operations = 0
        self.query_operations = 0

        # Current state gauges
        self.active_pools_by_tf: dict[str, int] = defaultdict(int)
        self.touched_pools_by_tf: dict[str, int] = defaultdict(int)
        self.expired_pools_by_tf: dict[str, int] = defaultdict(int)

        # Performance timing (in microseconds)
        self.total_add_time_us = 0
        self.total_touch_time_us = 0
        self.total_query_time_us = 0

    def record_pool_created(self, timeframe: str) -> None:
        """Record pool creation."""
        self.pools_created += 1
        self.active_pools_by_tf[timeframe] += 1

    def record_pool_touched(self, timeframe: str) -> None:
        """Record pool touch event."""
        self.pools_touched += 1
        self.active_pools_by_tf[timeframe] -= 1
        self.touched_pools_by_tf[timeframe] += 1

    def record_pool_expired(self, timeframe: str, from_state: PoolState) -> None:
        """Record pool expiry."""
        self.pools_expired += 1
        if from_state == PoolState.ACTIVE:
            self.active_pools_by_tf[timeframe] -= 1
        elif from_state == PoolState.TOUCHED:
            self.touched_pools_by_tf[timeframe] -= 1
        self.expired_pools_by_tf[timeframe] += 1

    def get_total_pools(self) -> int:
        """Get total number of tracked pools."""
        return (
            sum(self.active_pools_by_tf.values())
            + sum(self.touched_pools_by_tf.values())
            + sum(self.expired_pools_by_tf.values())
        )

    def get_prometheus_metrics(self) -> dict[str, float]:
        """Return metrics in Prometheus format."""
        metrics = {
            # Counters
            "pool_registry_pools_created_total": float(self.pools_created),
            "pool_registry_pools_touched_total": float(self.pools_touched),
            "pool_registry_pools_expired_total": float(self.pools_expired),
            "pool_registry_pools_cleaned_total": float(self.pools_cleaned),
            # Gauges
            "pool_registry_active_pools": float(sum(self.active_pools_by_tf.values())),
            "pool_registry_touched_pools": float(
                sum(self.touched_pools_by_tf.values())
            ),
            "pool_registry_expired_pools": float(
                sum(self.expired_pools_by_tf.values())
            ),
            "pool_registry_total_pools": float(self.get_total_pools()),
            # Performance
            "pool_registry_add_operations_total": float(self.add_operations),
            "pool_registry_touch_operations_total": float(self.touch_operations),
            "pool_registry_query_operations_total": float(self.query_operations),
        }

        # Add per-timeframe metrics
        for tf in set(
            list(self.active_pools_by_tf.keys())
            + list(self.touched_pools_by_tf.keys())
            + list(self.expired_pools_by_tf.keys())
        ):
            metrics[f"pool_registry_active_pools_tf_{tf.lower()}"] = float(
                self.active_pools_by_tf[tf]
            )
            metrics[f"pool_registry_touched_pools_tf_{tf.lower()}"] = float(
                self.touched_pools_by_tf[tf]
            )
            metrics[f"pool_registry_expired_pools_tf_{tf.lower()}"] = float(
                self.expired_pools_by_tf[tf]
            )

        return metrics


class PoolRegistry:
    """
    High-performance registry for liquidity pool lifecycle management.

    Features:
    - O(1) CRUD operations via hash maps
    - Automatic TTL expiry via timing wheel
    - Multi-timeframe isolation
    - Grace period for analytics
    - Prometheus-style metrics
    """

    def __init__(
        self,
        config: PoolRegistryConfig | None = None,
        wheel_config: WheelConfig | None = None,
        current_time: datetime | None = None,
    ):
        """
        Initialize pool registry.

        Args:
            config: Registry configuration
            wheel_config: TTL wheel configuration
            current_time: Initial time (for testing)
        """
        self.config = config or PoolRegistryConfig()
        self.metrics = PoolRegistryMetrics() if self.config.enable_metrics else None

        # Core storage - O(1) access by pool_id
        self._pools: dict[str, LiquidityPool] = {}

        # Multi-timeframe indexing for isolation
        self._pools_by_tf: dict[str, set[str]] = defaultdict(set)

        # State-based indexing for fast queries
        self._pools_by_state: dict[PoolState, set[str]] = defaultdict(set)

        # TTL management
        self._ttl_wheel = TimerWheel(wheel_config)
        if current_time:
            self._ttl_wheel.current_time = current_time

        # Grace period tracking for analytics
        self._grace_pools: dict[str, datetime] = {}  # pool_id -> cleanup_time
        self._last_cleanup = self._ttl_wheel.current_time

        logger.info(
            f"PoolRegistry initialized with {self.config.max_pools_per_tf} max pools per TF"
        )

    def add(
        self,
        timeframe: str,
        top: float,
        bottom: float,
        strength: float,
        ttl: timedelta,
        hit_tolerance: float = 0.0,
        created_at: datetime | None = None,
    ) -> tuple[bool, str]:
        """
        Add a new liquidity pool.

        Args:
            timeframe: Pool timeframe (H1, H4, D1)
            top: Top price of the zone
            bottom: Bottom price of the zone
            strength: Detector strength for overlap weighting
            ttl: Time-to-live for the pool
            hit_tolerance: Price tolerance for zone hits
            created_at: Creation timestamp (defaults to current time)

        Returns:
            Tuple of (success: bool, pool_id: str)
        """
        import time

        start_time = time.perf_counter()

        try:
            # Validate timeframe capacity
            if len(self._pools_by_tf[timeframe]) >= self.config.max_pools_per_tf:
                logger.warning(
                    f"Timeframe {timeframe} at capacity ({self.config.max_pools_per_tf} pools)"
                )
                return False, ""

            # Generate unique pool ID
            created_at = created_at or self._ttl_wheel.current_time
            pool_id = generate_pool_id(timeframe, created_at, top, bottom)

            # Check for duplicates
            if pool_id in self._pools:
                logger.debug(f"Pool {pool_id} already exists")
                return False, pool_id

            # Calculate expiry time
            expires_at = created_at + ttl

            # Create pool object
            pool = LiquidityPool(
                pool_id=pool_id,
                timeframe=timeframe,
                top=top,
                bottom=bottom,
                strength=strength,
                state=PoolState.ACTIVE,
                created_at=created_at,
                last_touched_at=None,
                expires_at=expires_at,
                hit_tolerance=hit_tolerance,
            )

            # Schedule TTL expiry
            scheduled = self._ttl_wheel.schedule(pool_id, expires_at, created_at)
            if not scheduled:
                logger.warning(f"Failed to schedule TTL for pool {pool_id}")
                return False, pool_id

            # Store in all indexes
            self._pools[pool_id] = pool
            self._pools_by_tf[timeframe].add(pool_id)
            self._pools_by_state[PoolState.ACTIVE].add(pool_id)

            # Update metrics
            if self.metrics:
                self.metrics.record_pool_created(timeframe)
                self.metrics.add_operations += 1
                self.metrics.total_add_time_us += int(
                    (time.perf_counter() - start_time) * 1_000_000
                )

            logger.debug(
                f"Created pool {pool_id} in {timeframe} expiring at {expires_at}"
            )
            return True, pool_id

        except Exception as e:
            logger.error(f"Failed to add pool: {e}")
            return False, ""

    def touch(
        self, pool_id: str, touch_price: float, touch_time: datetime | None = None
    ) -> bool:
        """
        Mark a pool as touched (price entered the zone).

        Args:
            pool_id: Pool to mark as touched
            touch_price: Price that entered the zone
            touch_time: When the touch occurred (defaults to current time)

        Returns:
            True if pool was touched successfully
        """
        import time

        start_time = time.perf_counter()

        try:
            pool = self._pools.get(pool_id)
            if not pool:
                logger.debug(f"Pool {pool_id} not found for touch")
                return False

            if pool.state != PoolState.ACTIVE:
                logger.debug(f"Pool {pool_id} not active (state: {pool.state})")
                return False

            # Validate price is in zone
            if not pool.is_price_in_zone(touch_price):
                logger.debug(
                    f"Price {touch_price} not in zone [{pool.bottom}, {pool.top}] for pool {pool_id}"
                )
                return False

            touch_time = touch_time or self._ttl_wheel.current_time

            # Update pool state
            touched_pool = pool.with_state(PoolState.TOUCHED, touch_time)
            self._pools[pool_id] = touched_pool

            # Update state indexes
            self._pools_by_state[PoolState.ACTIVE].discard(pool_id)
            self._pools_by_state[PoolState.TOUCHED].add(pool_id)

            # Update metrics
            if self.metrics:
                self.metrics.record_pool_touched(pool.timeframe)
                self.metrics.touch_operations += 1
                self.metrics.total_touch_time_us += int(
                    (time.perf_counter() - start_time) * 1_000_000
                )

            logger.debug(f"Touched pool {pool_id} at price {touch_price}")
            return True

        except Exception as e:
            logger.error(f"Failed to touch pool {pool_id}: {e}")
            return False

    def expire_due(self, now: datetime) -> list[PoolExpiredEvent]:
        """
        Process pools that should be expired by the given time.

        Args:
            now: Current time for expiry checking

        Returns:
            List of expiry events generated
        """
        # Advance TTL wheel and get expired pool IDs
        expired_items = self._ttl_wheel.tick(now)
        events = []

        for item in expired_items:
            pool = self._pools.get(item.pool_id)
            if not pool:
                continue  # Already removed

            # Move to expired state
            expired_pool = pool.with_state(PoolState.EXPIRED)
            self._pools[item.pool_id] = expired_pool

            # Update state indexes
            self._pools_by_state[pool.state].discard(item.pool_id)
            self._pools_by_state[PoolState.EXPIRED].add(item.pool_id)

            # Schedule for grace period cleanup
            cleanup_time = now + self.config.grace_period
            self._grace_pools[item.pool_id] = cleanup_time

            # Create expiry event
            event = PoolExpiredEvent(
                pool_id=item.pool_id, timestamp=now, final_state=pool.state
            )
            events.append(event)

            # Update metrics
            if self.metrics:
                self.metrics.record_pool_expired(pool.timeframe, pool.state)

            logger.debug(f"Expired pool {item.pool_id} (was {pool.state})")

        # Periodic grace period cleanup
        if now - self._last_cleanup >= self.config.cleanup_interval:
            self._cleanup_grace_period(now)
            self._last_cleanup = now

        return events

    def query_active(
        self, side: str | None = None, timeframe: str | None = None
    ) -> list[LiquidityPool]:
        """
        Query active pools with optional filtering.

        Args:
            side: Filter by side ("bid" or "ask") - future enhancement
            timeframe: Filter by timeframe (H1, H4, D1)

        Returns:
            List of matching active pools
        """
        import time

        start_time = time.perf_counter()

        try:
            # Start with active pools
            active_pool_ids = self._pools_by_state[PoolState.ACTIVE].copy()

            # Apply timeframe filter
            if timeframe:
                tf_pool_ids = self._pools_by_tf[timeframe]
                active_pool_ids &= tf_pool_ids

            # Get pool objects
            pools = [
                self._pools[pool_id]
                for pool_id in active_pool_ids
                if pool_id in self._pools
            ]

            # Update metrics
            if self.metrics:
                self.metrics.query_operations += 1
                self.metrics.total_query_time_us += int(
                    (time.perf_counter() - start_time) * 1_000_000
                )

            return pools

        except Exception as e:
            logger.error(f"Failed to query active pools: {e}")
            return []

    def get_pool(self, pool_id: str) -> LiquidityPool | None:
        """Get a specific pool by ID."""
        return self._pools.get(pool_id)

    def remove(self, pool_id: str) -> bool:
        """
        Remove a pool from the registry.

        Args:
            pool_id: Pool to remove

        Returns:
            True if pool was removed successfully
        """
        pool = self._pools.get(pool_id)
        if not pool:
            return False

        # Cancel TTL if still scheduled
        self._ttl_wheel.cancel(pool_id)

        # Remove from all indexes
        del self._pools[pool_id]
        self._pools_by_tf[pool.timeframe].discard(pool_id)
        self._pools_by_state[pool.state].discard(pool_id)
        self._grace_pools.pop(pool_id, None)

        logger.debug(f"Removed pool {pool_id}")
        return True

    def size(self) -> int:
        """Return total number of pools in registry."""
        return len(self._pools)

    def size_by_timeframe(self, timeframe: str) -> int:
        """Return number of pools for a specific timeframe."""
        return len(self._pools_by_tf[timeframe])

    def size_by_state(self, state: PoolState) -> int:
        """Return number of pools in a specific state."""
        return len(self._pools_by_state[state])

    def get_metrics(self) -> dict[str, Any]:
        """Return registry performance metrics."""
        base_metrics = {
            "total_pools": self.size(),
            "ttl_wheel_metrics": self._ttl_wheel.get_metrics(),
            "grace_pools": len(self._grace_pools),
            "timeframes": dict(self._pools_by_tf),
            "states": {
                state.value: len(pool_ids)
                for state, pool_ids in self._pools_by_state.items()
            },
        }

        if self.metrics:
            base_metrics["prometheus"] = self.metrics.get_prometheus_metrics()

        return base_metrics

    def _cleanup_grace_period(self, now: datetime) -> None:
        """Clean up pools that have exceeded grace period."""
        to_cleanup = []

        for pool_id, cleanup_time in self._grace_pools.items():
            if now >= cleanup_time:
                to_cleanup.append(pool_id)

        for pool_id in to_cleanup:
            if self.remove(pool_id):
                if self.metrics:
                    self.metrics.pools_cleaned += 1
                logger.debug(f"Cleaned up grace period pool {pool_id}")
