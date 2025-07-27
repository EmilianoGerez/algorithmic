"""
Live position reconciler for maintaining sync with broker state.

This module provides real-time position reconciliation between local trading
state and broker positions to prevent drift and ensure consistency.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from core.trading.models import Position

__all__ = ["LiveReconciler", "BrokerInterface", "ReconciliationConfig"]

logger = logging.getLogger(__name__)


class ReconciliationConfig:
    """Configuration for live position reconciliation."""

    def __init__(
        self,
        drift_threshold: float = 0.01,  # 1% drift threshold
        check_interval: float = 30.0,  # 30 second intervals
        reconcile_interval: float = 30.0,  # Alias for check_interval for compatibility
        position_tolerance: float = 1e-6,  # Position tolerance for exact matches
        max_drift_history: int = 100,  # Keep last 100 drift records
        history_retention_hours: int = 24,  # Keep 24 hours of history
    ) -> None:
        self.drift_threshold = drift_threshold
        self.check_interval = check_interval
        self.reconcile_interval = (
            reconcile_interval or check_interval
        )  # For compatibility
        self.position_tolerance = position_tolerance
        self.max_drift_history = max_drift_history
        self.history_retention_hours = history_retention_hours


class BrokerInterface(Protocol):
    """Protocol for broker interfaces that support position queries."""

    async def positions(self) -> list[Position]:
        """Get current positions from broker."""
        ...

    async def account(self) -> Any:
        """Get account information from broker."""
        ...


class PositionDrift:
    """Represents a detected drift between local and broker positions."""

    def __init__(
        self,
        symbol: str,
        local_quantity: Decimal,
        broker_quantity: Decimal,
        drift_amount: Decimal,
        timestamp: datetime,
    ) -> None:
        self.symbol = symbol
        self.local_quantity = local_quantity
        self.broker_quantity = broker_quantity
        self.drift_amount = drift_amount
        self.timestamp = timestamp

    @property
    def drift_percentage(self) -> float:
        """Calculate drift as percentage of broker position."""
        if self.broker_quantity == 0:
            return 100.0 if self.local_quantity != 0 else 0.0
        return float(abs(self.drift_amount) / abs(self.broker_quantity) * 100)

    def __str__(self) -> str:
        return (
            f"Drift in {self.symbol}: "
            f"local={self.local_quantity}, "
            f"broker={self.broker_quantity}, "
            f"drift={self.drift_amount} ({self.drift_percentage:.1f}%)"
        )


class LiveReconciler:
    """Live position reconciler for broker synchronization.

    Monitors positions every 30 seconds and detects drift between local
    tracking and broker actual positions. Provides alerts and correction
    mechanisms to maintain system integrity.
    """

    def __init__(
        self,
        broker: BrokerInterface,
        config: ReconciliationConfig | None = None,
        drift_threshold: float | None = None,  # For backward compatibility
        check_interval: float | None = None,  # For backward compatibility
    ) -> None:
        """Initialize live reconciler.

        Args:
            broker: Broker interface for position queries
            config: Reconciliation configuration
            drift_threshold: Deprecated, use config instead
            check_interval: Deprecated, use config instead
        """
        self.broker = broker

        # Handle backward compatibility
        if config is None:
            config = ReconciliationConfig(
                drift_threshold=drift_threshold or 0.01,
                check_interval=check_interval or 30.0,
            )

        self.config = config
        self.drift_threshold = config.drift_threshold
        self.check_interval = config.check_interval

        self._local_positions: dict[str, Position] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._drift_history: list[PositionDrift] = []

        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def start(self) -> None:
        """Start the reconciliation loop."""
        if self._running:
            self.logger.warning("Reconciler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._reconciliation_loop())
        self.logger.info(
            f"Started live reconciler (check_interval={self.check_interval}s)"
        )

    async def stop(self) -> None:
        """Stop the reconciliation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self.logger.info("Stopped live reconciler")

    def update_local_position(self, position: Position) -> None:
        """Update local position tracking.

        Args:
            position: Position to update in local tracking
        """
        self._local_positions[position.symbol] = position

    def remove_local_position(self, symbol: str) -> None:
        """Remove position from local tracking.

        Args:
            symbol: Symbol to remove
        """
        self._local_positions.pop(symbol, None)

    async def check_drift(self) -> list[PositionDrift]:
        """Check for position drift between local and broker.

        Returns:
            List of detected position drifts
        """
        try:
            broker_positions = await self.broker.positions()
            broker_pos_map = {pos.symbol: pos for pos in broker_positions}

            drifts = []
            all_symbols = set(self._local_positions.keys()) | set(broker_pos_map.keys())

            for symbol in all_symbols:
                local_pos = self._local_positions.get(symbol)
                broker_pos = broker_pos_map.get(symbol)

                local_qty = local_pos.quantity if local_pos else Decimal("0")
                broker_qty = broker_pos.quantity if broker_pos else Decimal("0")

                drift_amount = local_qty - broker_qty

                if drift_amount != 0:
                    drift = PositionDrift(
                        symbol=symbol,
                        local_quantity=local_qty,
                        broker_quantity=broker_qty,
                        drift_amount=drift_amount,
                        timestamp=datetime.now(),
                    )

                    # Check if drift exceeds threshold
                    if drift.drift_percentage >= (self.drift_threshold * 100):
                        drifts.append(drift)
                        self.logger.warning(f"Position drift detected: {drift}")

            return drifts

        except Exception as e:
            self.logger.error(f"Failed to check position drift: {e}")
            return []

    async def force_reconciliation(self) -> dict[str, Any]:
        """Force immediate reconciliation check.

        Returns:
            Dictionary with reconciliation results
        """
        self.logger.info("Forcing immediate reconciliation")

        try:
            # Get current broker state
            broker_positions = await self.broker.positions()
            account_info = await self.broker.account()
            drifts = await self.check_drift()

            result = {
                "timestamp": datetime.now().isoformat(),
                "broker_positions": len(broker_positions),
                "local_positions": len(self._local_positions),
                "detected_drifts": len(drifts),
                "drifts": [
                    {
                        "symbol": drift.symbol,
                        "local_qty": float(drift.local_quantity),
                        "broker_qty": float(drift.broker_quantity),
                        "drift_amount": float(drift.drift_amount),
                        "drift_percentage": drift.drift_percentage,
                    }
                    for drift in drifts
                ],
                "account_equity": getattr(account_info, "equity", None),
            }

            # Store drifts in history
            self._drift_history.extend(drifts)

            # Keep only last N drift records
            if len(self._drift_history) > self.config.max_drift_history:
                self._drift_history = self._drift_history[
                    -self.config.max_drift_history :
                ]

            return result

        except Exception as e:
            self.logger.error(f"Force reconciliation failed: {e}")
            raise

    def get_drift_history(self, since: datetime | None = None) -> list[PositionDrift]:
        """Get historical drift records.

        Args:
            since: Only return drifts after this timestamp

        Returns:
            List of historical drift records
        """
        if since is None:
            return self._drift_history.copy()

        return [drift for drift in self._drift_history if drift.timestamp >= since]

    async def _reconciliation_loop(self) -> None:
        """Main reconciliation loop."""
        self.logger.info("Starting reconciliation loop")

        while self._running:
            try:
                # Perform drift check
                drifts = await self.check_drift()

                if drifts:
                    self.logger.warning(f"Detected {len(drifts)} position drifts")
                    for drift in drifts:
                        self.logger.warning(f"  {drift}")

                # Store in history
                self._drift_history.extend(drifts)

                # Keep only recent history
                cutoff_time = datetime.now() - timedelta(
                    hours=self.config.history_retention_hours
                )
                self._drift_history = [
                    drift
                    for drift in self._drift_history
                    if drift.timestamp >= cutoff_time
                ]

                # Wait for next check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in reconciliation loop: {e}")
                # Wait before retrying
                await asyncio.sleep(min(self.check_interval, 30.0))

        self.logger.info("Reconciliation loop stopped")

    def __repr__(self) -> str:
        return (
            f"LiveReconciler(running={self._running}, "
            f"positions={len(self._local_positions)}, "
            f"threshold={self.drift_threshold * 100:.1f}%)"
        )
