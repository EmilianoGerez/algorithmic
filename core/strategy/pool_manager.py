"""
Integration layer for converting detector events to liquidity pools.

Handles the critical path of mapping FVG/Pivot events from detectors
into pool registry entries with proper TTL and strength mapping.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ..detectors.events import LiquidityPoolEvent
from .pool_models import PoolCreatedEvent, PoolExpiredEvent, PoolTouchedEvent
from .pool_registry import PoolRegistry

__all__ = ["PoolManager", "PoolManagerConfig", "EventMappingResult"]


logger = logging.getLogger(__name__)


class PoolManagerConfig:
    """Configuration for pool manager behavior."""

    def __init__(
        self,
        ttl_by_timeframe: dict[str, timedelta] | None = None,
        hit_tolerance_by_timeframe: dict[str, float] | None = None,
        strength_threshold: float = 0.1,
        auto_expire_check_interval: timedelta = timedelta(seconds=30),
        enable_event_logging: bool = True,
    ):
        """
        Initialize pool manager configuration.

        Args:
            ttl_by_timeframe: TTL settings per timeframe
            hit_tolerance_by_timeframe: Hit tolerance per timeframe
            strength_threshold: Minimum strength to create pools
            auto_expire_check_interval: How often to check for expiries
            enable_event_logging: Log pool lifecycle events
        """
        # Default TTL configuration matching roadmap guidance
        self.ttl_by_timeframe = ttl_by_timeframe or {
            "H1": timedelta(minutes=120),  # 2 hours
            "H4": timedelta(hours=6),  # 6 hours
            "D1": timedelta(days=2),  # 2 days
        }

        # Default hit tolerance (0 = exact price matching)
        self.hit_tolerance_by_timeframe = hit_tolerance_by_timeframe or {
            "H1": 0.0,
            "H4": 0.0,
            "D1": 0.0,
        }

        self.strength_threshold = strength_threshold
        self.auto_expire_check_interval = auto_expire_check_interval
        self.enable_event_logging = enable_event_logging

    def get_ttl_for_timeframe(self, timeframe: str) -> timedelta:
        """Get TTL for a specific timeframe."""
        return self.ttl_by_timeframe.get(timeframe, timedelta(minutes=120))

    def get_hit_tolerance_for_timeframe(self, timeframe: str) -> float:
        """Get hit tolerance for a specific timeframe."""
        return self.hit_tolerance_by_timeframe.get(timeframe, 0.0)


class EventMappingResult:
    """Result of mapping a detector event to pool operations."""

    def __init__(
        self,
        success: bool,
        pool_id: str = "",
        reason: str = "",
        pool_created: bool = False,
        pool_touched: bool = False,
    ):
        """
        Initialize mapping result.

        Args:
            success: Whether mapping was successful
            pool_id: ID of affected pool
            reason: Reason for failure (if success=False)
            pool_created: Whether a new pool was created
            pool_touched: Whether an existing pool was touched
        """
        self.success = success
        self.pool_id = pool_id
        self.reason = reason
        self.pool_created = pool_created
        self.pool_touched = pool_touched


class PoolManager:
    """
    High-level manager for converting detector events to pool operations.

    Handles:
    - Converting FVG/Pivot events to pool creation
    - Mapping price touches to pool state updates
    - Automatic expiry processing
    - Event lifecycle coordination
    """

    def __init__(self, registry: PoolRegistry, config: PoolManagerConfig | None = None):
        """
        Initialize pool manager.

        Args:
            registry: Pool registry for storage operations
            config: Manager configuration
        """
        self.registry = registry
        self.config = config or PoolManagerConfig()
        self._last_expiry_check = datetime.now()
        self.zone_watcher = None  # Will be set by factory during wiring

        logger.info(
            f"PoolManager initialized with TTLs: {self.config.ttl_by_timeframe}"
        )

    def process_detector_event(self, event: LiquidityPoolEvent) -> EventMappingResult:
        """
        Process a detector event and convert to pool operations.

        Args:
            event: Detector event (FVG, Pivot, etc.)

        Returns:
            Result of the mapping operation
        """
        try:
            # Validate event strength
            if (
                hasattr(event, "strength")
                and event.strength < self.config.strength_threshold
            ):
                return EventMappingResult(
                    success=False,
                    reason=f"Event strength {event.strength} below threshold {self.config.strength_threshold}",
                )

            # Extract zone coordinates from event
            top, bottom = self._extract_zone_coordinates(event)
            if top is None or bottom is None:
                return EventMappingResult(
                    success=False,
                    reason="Failed to extract valid zone coordinates from event",
                )

            # Get configuration for this timeframe
            ttl = self.config.get_ttl_for_timeframe(event.tf)
            hit_tolerance = self.config.get_hit_tolerance_for_timeframe(event.tf)

            # Extract strength (default to 1.0 if not available)
            strength = getattr(event, "strength", 1.0)

            # Create pool in registry
            success, pool_id = self.registry.add(
                timeframe=event.tf,
                top=top,
                bottom=bottom,
                strength=strength,
                ttl=ttl,
                hit_tolerance=hit_tolerance,
                created_at=event.ts,
            )

            if success:
                if self.config.enable_event_logging:
                    logger.info(
                        f"Created pool {pool_id} from {type(event).__name__} "
                        f"in {event.tf} at [{bottom:.5f}, {top:.5f}] "
                        f"strength={strength:.3f} ttl={ttl}"
                    )

                # Emit PoolCreatedEvent to ZoneWatcher if connected
                if hasattr(self, 'zone_watcher') and self.zone_watcher:
                    # Get the created pool from registry
                    pool = self.registry.get_pool(pool_id)
                    if pool:
                        pool_created_event = PoolCreatedEvent(
                            pool_id=pool_id,
                            timestamp=event.ts,
                            pool=pool
                        )
                        self.zone_watcher.on_pool_event(pool_created_event)

                return EventMappingResult(
                    success=True, pool_id=pool_id, pool_created=True
                )
            else:
                return EventMappingResult(
                    success=False,
                    reason="Registry rejected pool creation (likely duplicate)",
                )

        except Exception as e:
            logger.error(f"Failed to process detector event: {e}")
            return EventMappingResult(success=False, reason=f"Processing error: {e!s}")

    def process_price_update(
        self, price: float, timestamp: datetime, timeframe: str | None = None
    ) -> list[PoolTouchedEvent]:
        """
        Process a price update and check for pool touches.

        Args:
            price: Current price
            timestamp: Price timestamp
            timeframe: Specific timeframe to check (None = all)

        Returns:
            List of touch events generated
        """
        touch_events = []

        try:
            # Get active pools for the timeframe
            active_pools = self.registry.query_active(timeframe=timeframe)

            for pool in active_pools:
                # Check if price is in pool zone
                if pool.is_price_in_zone(price) and pool.state.value == "active":
                    # Mark pool as touched
                    touched = self.registry.touch(pool.pool_id, price, timestamp)

                    if touched:
                        touch_event = PoolTouchedEvent(
                            pool_id=pool.pool_id, timestamp=timestamp, touch_price=price
                        )
                        touch_events.append(touch_event)

                        if self.config.enable_event_logging:
                            logger.info(
                                f"Pool {pool.pool_id} touched at price {price:.5f}"
                            )

        except Exception as e:
            logger.error(f"Failed to process price update: {e}")

        return touch_events

    def process_expiries(self, current_time: datetime) -> list[PoolExpiredEvent]:
        """
        Process pool expiries for the current time.

        Args:
            current_time: Current time for expiry checking

        Returns:
            List of expiry events generated
        """
        try:
            # Process expiries through registry
            expiry_events = self.registry.expire_due(current_time)

            if expiry_events and self.config.enable_event_logging:
                logger.info(
                    f"Processed {len(expiry_events)} pool expiries at {current_time}"
                )

            self._last_expiry_check = current_time
            return expiry_events

        except Exception as e:
            logger.error(f"Failed to process expiries: {e}")
            return []

    def auto_process_expiries(self, current_time: datetime) -> list[PoolExpiredEvent]:
        """
        Automatically process expiries if interval has passed.

        Args:
            current_time: Current time

        Returns:
            List of expiry events if processing occurred
        """
        if (
            current_time - self._last_expiry_check
            >= self.config.auto_expire_check_interval
        ):
            return self.process_expiries(current_time)
        return []

    def batch_process_events(
        self, events: list[LiquidityPoolEvent]
    ) -> tuple[list[EventMappingResult], list[PoolCreatedEvent]]:
        """
        Process multiple detector events in batch.

        Args:
            events: List of detector events to process

        Returns:
            Tuple of (mapping_results, created_events)
        """
        mapping_results = []
        created_events = []

        for event in events:
            result = self.process_detector_event(event)
            mapping_results.append(result)

            # Generate created event if pool was created
            if result.pool_created:
                pool = self.registry.get_pool(result.pool_id)
                if pool:
                    created_event = PoolCreatedEvent(
                        pool_id=result.pool_id, timestamp=event.ts, pool=pool
                    )
                    created_events.append(created_event)

        return mapping_results, created_events

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics."""
        registry_metrics = self.registry.get_metrics()

        return {
            "config": {
                "ttl_by_timeframe": {
                    tf: str(ttl) for tf, ttl in self.config.ttl_by_timeframe.items()
                },
                "hit_tolerance_by_timeframe": self.config.hit_tolerance_by_timeframe,
                "strength_threshold": self.config.strength_threshold,
            },
            "registry_metrics": registry_metrics,
            "last_expiry_check": self._last_expiry_check.isoformat(),
        }

    def _extract_zone_coordinates(
        self, event: LiquidityPoolEvent
    ) -> tuple[float | None, float | None]:
        """
        Extract top and bottom coordinates from detector event.

        Args:
            event: Detector event

        Returns:
            Tuple of (top, bottom) prices or (None, None) if invalid
        """
        try:
            # Handle FVG events
            if hasattr(event, "gap_top") and hasattr(event, "gap_bottom"):
                return event.gap_top, event.gap_bottom

            # Handle Pivot events
            if hasattr(event, "pivot_price") and hasattr(event, "atr_distance"):
                pivot_price = event.pivot_price
                atr_distance = event.atr_distance

                # Create zone around pivot (±0.5 ATR)
                half_atr = atr_distance * 0.5
                return pivot_price + half_atr, pivot_price - half_atr

            # Handle generic events with top/bottom
            if hasattr(event, "top") and hasattr(event, "bottom"):
                return event.top, event.bottom

            # Handle events with price and size
            if hasattr(event, "price") and hasattr(event, "zone_size"):
                price = event.price
                half_size = event.zone_size * 0.5
                return price + half_size, price - half_size

            # Fallback: log available attributes for debugging
            available_attrs = [attr for attr in dir(event) if not attr.startswith("_")]
            logger.warning(
                f"Could not extract zone coordinates from {type(event).__name__}. "
                f"Available attributes: {available_attrs}"
            )

            return None, None

        except Exception as e:
            logger.error(f"Error extracting zone coordinates: {e}")
            return None, None
